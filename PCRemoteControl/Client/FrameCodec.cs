using System.Drawing.Imaging;

namespace PCRemoteControl;

sealed record CapturedFrame(byte[] Data, int Width, int Height, bool NearlyBlack);

static class FrameCodec
{
    // GDI screen copies do not define alpha. Keep the entire capture/resize path opaque.
    public static Bitmap CreateSurface(int width, int height) => new(width, height, PixelFormat.Format24bppRgb);

    public static CapturedFrame Encode(Bitmap original)
    {
        double scale = Math.Min(1, 1600.0 / original.Width);
        using var resized = CreateSurface(Math.Max(1, (int)(original.Width * scale)), Math.Max(1, (int)(original.Height * scale)));
        using (var g = Graphics.FromImage(resized))
            g.DrawImage(original, new Rectangle(0, 0, resized.Width, resized.Height));
        bool black = true;
        for (int y = 0; y < 12 && black; y++)
            for (int x = 0; x < 12 && black; x++)
            {
                Color color = resized.GetPixel(x * (resized.Width - 1) / 11, y * (resized.Height - 1) / 11);
                black = color.R < 4 && color.G < 4 && color.B < 4;
            }
        using var buffer = new MemoryStream();
        using var parameters = new EncoderParameters(1);
        parameters.Param[0] = new EncoderParameter(System.Drawing.Imaging.Encoder.Quality, 65L);
        resized.Save(buffer, ImageCodecInfo.GetImageEncoders().First(c => c.FormatID == ImageFormat.Jpeg.Guid), parameters);
        return new CapturedFrame(buffer.ToArray(), resized.Width, resized.Height, black);
    }

    public static Bitmap Decode(byte[] data)
    {
        if (data.Length == 0) throw new IOException("빈 화면 데이터입니다.");
        using var buffer = new MemoryStream(data);
        using var decoded = Image.FromStream(buffer, false, true);
        if ((long)decoded.Width * decoded.Height > 40_000_000)
            throw new IOException("화면 해상도가 허용 범위를 초과했습니다.");
        return new Bitmap(decoded);
    }
}
