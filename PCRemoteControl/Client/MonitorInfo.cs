namespace PCRemoteControl;

sealed record MonitorInfo(string Id, int X, int Y, int Width, int Height, bool Primary)
{
    public Rectangle Bounds => new(X, Y, Width, Height);
    public string Label => $"모니터 {Id.Replace(@"\\.\DISPLAY", "")} · {Width}×{Height}{(Primary ? " (주 화면)" : "")}";
    public static MonitorInfo[] GetAll() => Screen.AllScreens
        .Select(s => new MonitorInfo(s.DeviceName, s.Bounds.X, s.Bounds.Y, s.Bounds.Width, s.Bounds.Height, s.Primary))
        .OrderBy(s => s.Id, StringComparer.OrdinalIgnoreCase).ToArray();
    public static MonitorInfo? Resolve(IEnumerable<MonitorInfo> screens, string? id) =>
        screens.FirstOrDefault(s => s.Id == id) ?? screens.FirstOrDefault(s => s.Primary) ?? screens.FirstOrDefault();
    public static Point MapInput(Rectangle screen, Rectangle desktop, double x, double y)
    {
        int px = screen.Left + (int)(Math.Clamp(x, 0, 1) * (screen.Width - 1));
        int py = screen.Top + (int)(Math.Clamp(y, 0, 1) * (screen.Height - 1));
        return new Point((int)((px - desktop.Left) * 65535L / Math.Max(1, desktop.Width - 1)),
            (int)((py - desktop.Top) * 65535L / Math.Max(1, desktop.Height - 1)));
    }
}
