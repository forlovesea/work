using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.ComponentModel;
using System.Text;

namespace PCRemoteControl;
static class Desktop
{
    [StructLayout(LayoutKind.Sequential)] struct MouseInput { public int x, y; public uint data, flags, time; public UIntPtr extra; }
    [StructLayout(LayoutKind.Sequential)] struct KeyInput { public ushort key, scan; public uint flags, time; public UIntPtr extra; }
    [StructLayout(LayoutKind.Explicit)] struct InputUnion { [FieldOffset(0)] public MouseInput mouse; [FieldOffset(0)] public KeyInput key; }
    [StructLayout(LayoutKind.Sequential)] struct Input { public uint type; public InputUnion value; }
    [DllImport("user32.dll", SetLastError = true)] static extern uint SendInput(uint count, Input[] inputs, int size);
    [DllImport("user32.dll", SetLastError = true)] static extern IntPtr GetDC(IntPtr hwnd);
    [DllImport("user32.dll")] static extern int ReleaseDC(IntPtr hwnd, IntPtr dc);
    [DllImport("gdi32.dll", SetLastError = true)] static extern bool BitBlt(IntPtr destination, int x, int y, int width, int height, IntPtr source, int sourceX, int sourceY, uint operation);
    [DllImport("user32.dll", SetLastError = true)] static extern IntPtr OpenInputDesktop(uint flags, bool inherit, uint access);
    [DllImport("user32.dll")] static extern bool CloseDesktop(IntPtr desktop);
    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)] static extern bool GetUserObjectInformation(IntPtr handle, int index, StringBuilder name, int bytes, out int required);
    [DllImport("user32.dll")] static extern IntPtr GetThreadDesktop(uint threadId);
    [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();
    static readonly HashSet<int> keys = new();
    static readonly HashSet<string> buttons = new();
    static void Send(Input input)
    {
        if (SendInput(1, new[] { input }, Marshal.SizeOf<Input>()) != 1)
            throw new IOException("Windows가 입력을 차단했습니다. 관리자 창/잠금 화면 여부를 확인하세요.");
    }
    static void Key(int code, bool down) => Send(new Input { type = 1, value = new InputUnion { key = new KeyInput { key = (ushort)code, flags = (down ? 0u : 2u) | (code is 33 or 34 or 35 or 36 or 37 or 38 or 39 or 40 or 45 or 46 or 91 or 92 or 111 or 163 or 165 ? 1u : 0u) } } });
    static uint ButtonFlag(string button, bool down) => button switch { "left" => down ? 2u : 4u, "right" => down ? 8u : 16u, "middle" => down ? 32u : 64u, _ => 0u };
    public static void Release()
    {
        foreach (int key in keys.ToArray()) { try { Key(key, false); } catch (IOException) { } }
        foreach (string button in buttons.ToArray()) { try { Send(new Input { value = new InputUnion { mouse = new MouseInput { flags = ButtonFlag(button, false) } } }); } catch (IOException) { } }
        keys.Clear(); buttons.Clear();
    }
    public static void Apply(JsonElement m)
    {
        string? action = m.GetProperty("action").GetString();
        if (action == "release") { Release(); return; }
        if (action == "key")
        {
            int code = m.GetProperty("key").GetInt32();
            if (code < 1 || code > 254) return;
            bool down = m.GetProperty("down").GetBoolean();
            Key(code, down);
            if (down) keys.Add(code); else keys.Remove(code);
            return;
        }
        if (action != "mouse") return;
        double x = m.GetProperty("x").GetDouble(), y = m.GetProperty("y").GetDouble();
        if (!double.IsFinite(x) || !double.IsFinite(y)) return;
        Rectangle primary = Screen.PrimaryScreen!.Bounds, all = SystemInformation.VirtualScreen;
        int px = primary.Left + (int)(Math.Clamp(x, 0, 1) * (primary.Width - 1));
        int py = primary.Top + (int)(Math.Clamp(y, 0, 1) * (primary.Height - 1));
        uint flags = 0x8000 | 0x4000 | 1, data = 0;
        if (m.TryGetProperty("button", out var b))
        {
            string button = b.GetString() ?? "";
            bool down = m.GetProperty("down").GetBoolean();
            flags |= ButtonFlag(button, down);
            if (down) buttons.Add(button); else buttons.Remove(button);
        }
        if (m.TryGetProperty("wheel", out var wheel)) { flags |= 0x800; data = unchecked((uint)Math.Clamp(wheel.GetInt32(), -1200, 1200)); }
        Send(new Input { value = new InputUnion { mouse = new MouseInput {
            x = (int)((px - all.Left) * 65535L / Math.Max(1, all.Width - 1)),
            y = (int)((py - all.Top) * 65535L / Math.Max(1, all.Height - 1)), flags = flags, data = data } } });
    }
    public static CapturedFrame Capture(Rectangle bounds)
    {
        if (bounds.Width <= 0 || bounds.Height <= 0) throw new IOException("활성 모니터를 찾을 수 없습니다.");
        IntPtr input = OpenInputDesktop(0, false, 1); // Read desktop metadata only; never switch desktops.
        if (input == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error(), "TARGET의 잠금 화면 또는 보안 화면을 해제하세요.");
        try
        {
            var inputName = new StringBuilder(256);
            var threadName = new StringBuilder(256);
            if (!GetUserObjectInformation(input, 2, inputName, 512, out _) ||
                !GetUserObjectInformation(GetThreadDesktop(GetCurrentThreadId()), 2, threadName, 512, out _))
                throw new Win32Exception(Marshal.GetLastWin32Error());
            if (!string.Equals(inputName.ToString(), threadName.ToString(), StringComparison.OrdinalIgnoreCase))
                throw new IOException("TARGET의 잠금 화면 또는 UAC 보안 화면을 해제하세요.");
        }
        finally { CloseDesktop(input); }
        using var original = FrameCodec.CreateSurface(bounds.Width, bounds.Height);
        using (var g = Graphics.FromImage(original))
        {
            IntPtr source = GetDC(IntPtr.Zero);
            if (source == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error());
            try
            {
                IntPtr destination = g.GetHdc();
                try
                {
                    const uint sourceCopy = 0x00CC0020, captureLayered = 0x40000000;
                    if (!BitBlt(destination, 0, 0, bounds.Width, bounds.Height, source, bounds.X, bounds.Y, sourceCopy | captureLayered) &&
                        !BitBlt(destination, 0, 0, bounds.Width, bounds.Height, source, bounds.X, bounds.Y, sourceCopy))
                        throw new Win32Exception(Marshal.GetLastWin32Error(), "화면 캡처 실패. TARGET 로그인 상태와 모니터 연결을 확인하세요.");
                }
                finally { g.ReleaseHdc(destination); }
            }
            finally { ReleaseDC(IntPtr.Zero, source); }
        }
        return FrameCodec.Encode(original);
    }
}
