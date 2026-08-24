using System.Text;
using TBC1000B.WinForms.Models;

namespace TBC1000B.WinForms.Services;

public sealed class TrapLogService
{
    private const string Header = "Time\tTrapOid\tOrdinalNumber\tAlarm\tLevel\tEquipmentId\tEquipmentName\tFatherEquipment\tIsResume";
    private readonly string _profileDirectory;
    private readonly object _gate = new();

    public TrapLogService(string rootDirectory, string profileFilePath)
    {
        var profileName = Path.GetFileNameWithoutExtension(profileFilePath);
        _profileDirectory = Path.Combine(rootDirectory, SafePathPart(profileName));
    }

    public string Append(TrapEntry entry)
    {
        lock (_gate)
        {
            Directory.CreateDirectory(_profileDirectory);
            var path = Path.Combine(_profileDirectory, $"trap-{entry.Time:yyyy-MM-dd}.log");
            var isNew = !File.Exists(path) || new FileInfo(path).Length == 0;
            using var writer = new StreamWriter(path, append: true, new UTF8Encoding(false));
            if (isNew) writer.WriteLine(Header);
            writer.WriteLine(string.Join('\t', new[]
            {
                entry.Time.ToString("yyyy-MM-dd HH:mm:ss.fff"), entry.Oid, entry.OrdinalNumber,
                entry.Alarm, entry.Level.ToString(), entry.EquipmentId, entry.EquipmentName,
                entry.FatherEquipment, entry.IsResume ? "1" : "0"
            }.Select(Escape)));
            return path;
        }
    }

    private static string Escape(string? value) => (value ?? "")
        .Replace("\\", "\\\\", StringComparison.Ordinal)
        .Replace("\t", "\\t", StringComparison.Ordinal)
        .Replace("\r", "\\r", StringComparison.Ordinal)
        .Replace("\n", "\\n", StringComparison.Ordinal);

    private static string SafePathPart(string value)
    {
        foreach (var invalid in Path.GetInvalidFileNameChars()) value = value.Replace(invalid, '_');
        return string.IsNullOrWhiteSpace(value) ? "default" : value.Trim();
    }
}
