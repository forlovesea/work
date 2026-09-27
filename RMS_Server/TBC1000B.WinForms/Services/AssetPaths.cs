namespace TBC1000B.WinForms.Services;

internal static class AssetPaths
{
    // IncludeAllContentForSelfExtract puts the assembly and Assets in the same
    // extraction directory. User data still belongs beside the original EXE.
#pragma warning disable IL3000
    internal static string DirectoryPath { get; } = Path.Combine(
        Path.GetDirectoryName(typeof(AssetPaths).Assembly.Location) is { Length: > 0 } directory
            ? directory : AppContext.BaseDirectory, "Assets");
#pragma warning restore IL3000
}
