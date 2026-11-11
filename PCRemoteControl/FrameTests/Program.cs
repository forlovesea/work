using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Reflection;
using PCRemoteControl;

static class Program
{
    [DllImport("gdi32.dll", SetLastError = true)]
    static extern bool BitBlt(IntPtr destination, int x, int y, int width, int height, IntPtr source, int sx, int sy, uint operation);
    [StructLayout(LayoutKind.Sequential)] struct BitmapInfo
    {
        public uint Size; public int Width, Height; public ushort Planes, Bits;
        public uint Compression, ImageSize; public int Xppm, Yppm; public uint Used, Important;
    }
    [DllImport("gdi32.dll")] static extern IntPtr CreateCompatibleDC(IntPtr dc);
    [DllImport("gdi32.dll")] static extern IntPtr CreateDIBSection(IntPtr dc, ref BitmapInfo info, uint usage, out IntPtr bits, IntPtr section, uint offset);
    [DllImport("gdi32.dll")] static extern IntPtr SelectObject(IntPtr dc, IntPtr obj);
    [DllImport("gdi32.dll")] static extern bool DeleteObject(IntPtr obj);
    [DllImport("gdi32.dll")] static extern bool DeleteDC(IntPtr dc);
    static void Check(bool condition, string name)
    {
        if (!condition) throw new Exception(name);
        Console.WriteLine("PASS " + name);
    }

    static void Copy(Bitmap destination)
    {
        // A native DIB is necessary: Graphics.GetHdc is intended for drawing, not reading a managed bitmap.
        var info = new BitmapInfo { Size = 40, Width = destination.Width, Height = -destination.Height, Planes = 1, Bits = 32 };
        IntPtr sh = CreateCompatibleDC(IntPtr.Zero);
        IntPtr dib = CreateDIBSection(sh, ref info, 0, out var bits, IntPtr.Zero, 0);
        if (sh == IntPtr.Zero || dib == IntPtr.Zero) throw new System.ComponentModel.Win32Exception();
        var pixels = new byte[destination.Width * destination.Height * 4];
        for (int i = 0; i < pixels.Length; i += 4) { pixels[i] = 35; pixels[i + 1] = 90; pixels[i + 2] = 230; }
        Marshal.Copy(pixels, 0, bits, pixels.Length);
        IntPtr previous = SelectObject(sh, dib);
        using var dg = Graphics.FromImage(destination);
        try
        {
            var dh = dg.GetHdc();
            try { if (!BitBlt(dh, 0, 0, destination.Width, destination.Height, sh, 0, 0, 0x00CC0020)) throw new System.ComponentModel.Win32Exception(); }
            finally { dg.ReleaseHdc(dh); }
        }
        finally { SelectObject(sh, previous); DeleteObject(dib); DeleteDC(sh); }
    }

    [STAThread]
    static int Main()
    {
        try { Run(); return 0; }
        catch (Exception ex) { Console.Error.WriteLine(ex); return 1; }
    }
    static void Run()
    {
        // Emulate a GDI display surface with RGB color but no alpha channel.
        using var legacy = new Bitmap(3200, 1800);
        Copy(legacy);
        using var legacyResized = new Bitmap(legacy, new Size(1600, 900));
        Color legacyColor = legacyResized.GetPixel(800, 450);
        Console.WriteLine($"Legacy GDI/resize pixel: A={legacyColor.A} R={legacyColor.R} G={legacyColor.G} B={legacyColor.B}");

        using var opaque = FrameCodec.CreateSurface(3200, 1800);
        Copy(opaque);
        var rawFrame = FrameCodec.ToVideoFrame(opaque);
        int rawOffset = (450 * rawFrame.Width + 800) * 3;
        Check(rawFrame.Width == 1600 && rawFrame.Height == 900 &&
            rawFrame.Data[rawOffset] == 35 && rawFrame.Data[rawOffset + 1] == 90 && rawFrame.Data[rawOffset + 2] == 230,
            "WebRTC raw BGR frames scale correctly without JPEG encoding");
        var defaultIce = WebRtcSession.ParseIceServers(null);
        Check(defaultIce.Count == 1 && defaultIce[0].urls == "stun:stun.cloudflare.com:3478",
            "WebRTC has a default STUN server");
        var configuredIce = WebRtcSession.ParseIceServers(
            """[{"urls":"turn:turn.example.com:3478","username":"user","credential":"secret"}]""");
        Check(configuredIce.Count == 1 && configuredIce[0].urls == "turn:turn.example.com:3478" &&
            configuredIce[0].username == "user", "WebRTC accepts configured TURN credentials");
        bool badIceRejected = false;
        try { WebRtcSession.ParseIceServers("""[{"urls":"https://invalid.example.com"}]"""); }
        catch (IOException) { badIceRejected = true; }
        Check(badIceRejected, "invalid ICE server configuration is rejected");
        var frame = FrameCodec.Encode(opaque);
        using var decoded = FrameCodec.Decode(frame.Data);
        Color actual = decoded.GetPixel(800, 450);
        Check(actual.R > 190 && actual.G > 50 && actual.B < 80, "GDI RGB survives JPEG resize with undefined source alpha");
        Check(decoded.Width == 1600 && decoded.Height == 900, "4K-class frame scales to 1600 with aspect ratio");
        Check(!frame.NearlyBlack, "colored frame is not reported as black");

        byte[] json = JsonSerializer.SerializeToUtf8Bytes(new { type = "frame", data = frame.Data });
        using var message = JsonDocument.Parse(json);
        using var roundTrip = FrameCodec.Decode(message.RootElement.GetProperty("data").GetBytesFromBase64());
        Check(roundTrip.GetPixel(800, 450).R > 190, "JSON Base64 frame decodes with visible pixels");
        using var black = FrameCodec.CreateSurface(320, 180);
        using (var g = Graphics.FromImage(black)) g.Clear(Color.Black);
        var blackFrame = FrameCodec.Encode(black);
        using var decodedBlack = FrameCodec.Decode(blackFrame.Data);
        Check(blackFrame.NearlyBlack && decodedBlack.Width == 320, "black frames remain valid and carry a diagnostic flag");
        bool rejected = false;
        try { using var ignored = FrameCodec.Decode(Array.Empty<byte>()); } catch (IOException) { rejected = true; }
        Check(rejected, "empty frame rejected");
        rejected = false;
        try { using var ignored = FrameCodec.Decode(new byte[] { 1, 2, 3 }); } catch (ArgumentException) { rejected = true; }
        Check(rejected, "invalid JPEG rejected");
        using var recovered = FrameCodec.Decode(frame.Data);
        Check(recovered.Width == 1600, "valid frame decodes after malformed frame");

        // Exercise the actual HOST receive handler without opening a network connection or visible window.
        using var host = new MainForm(false);
        const BindingFlags fields = BindingFlags.NonPublic | BindingFlags.Instance;
        var handler = typeof(MainForm).GetMethod("HandleMessage", fields)!;
        void Receive(object value)
        {
            using var doc = JsonDocument.Parse(JsonSerializer.SerializeToUtf8Bytes(value));
            handler.Invoke(host, new object[] { doc.RootElement });
        }
        var view = (PictureBox)typeof(MainForm).GetField("view", fields)!.GetValue(host)!;
        typeof(MainForm).GetField("paired", fields)!.SetValue(host, true);
        Receive(new { type = "frame", data = frame.Data });
        Check(view.Image != null && view.Image.Width == 1600, "HOST receive handler assigns decoded image");
        Receive(new { type = "frame", data = Array.Empty<byte>(), capture_error = "Desktop locked" });
        Check(view.Image == null && ((RemoteView)view).Message.Contains("Desktop locked"), "TARGET failure replaces stale image with explanation");
        Receive(new { type = "frame", data = frame.Data });
        Check(view.Image != null, "HOST display recovers on next valid frame");
        typeof(MainForm).GetField("lastFrameAt", fields)!.SetValue(host, Environment.TickCount64 - 11000);
        typeof(MainForm).GetMethod("CheckFrameHealth", fields)!.Invoke(host, null);
        Check(view.Image == null && ((RemoteView)view).Message.Contains("10초"), "stale HOST frame is cleared after timeout");
        Receive(new { type = "frame", data = frame.Data });
        Check(view.Image != null, "HOST display recovers after timeout");
        Receive(new { type = "ended" });
        Check(view.Image == null, "session end clears displayed image");
        // No FormClosed event for a form that was never shown.
        foreach (string timerName in new[] { "health", "heartbeat", "capture", "listing" })
            ((System.Windows.Forms.Timer)typeof(MainForm).GetField(timerName, fields)!.GetValue(host)!).Dispose();
        ((ToolTip)typeof(MainForm).GetField("passwordTip", fields)!.GetValue(host)!).Dispose();
    }
}
