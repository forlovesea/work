using TBC1000B.WinForms.Models;

namespace TBC1000B.WinForms.Services;

public static class TrapDataParser
{
    private static readonly Dictionary<string, string> Names = new(StringComparer.Ordinal) {
        ["1.3.6.1.4.1.2011.6.164.2.1.3.0.99"] = "hwAcbAlarmTrap", ["1.3.6.1.4.1.2011.6.164.2.1.3.0.100"] = "hwAcbAlarmResumeTrap",
        ["1.3.6.1.4.1.2011.6.164.2.1.15.0.1"] = "hwCabinetAlarmTrap", ["1.3.6.1.4.1.2011.6.164.2.1.15.0.2"] = "hwCabinetAlarmResumeTrap",
        ["1.3.6.1.4.1.2011.6.164.2.1.2.0.99"] = "hwAcbGroupAlarmTrap", ["1.3.6.1.4.1.2011.6.164.2.1.2.0.100"] = "hwAcbGroupAlarmResumeTrap" };
    private static readonly HashSet<string> ResumeOids = ["1.3.6.1.4.1.2011.6.164.2.1.2.0.100", "1.3.6.1.4.1.2011.6.164.2.1.3.0.100", "1.3.6.1.4.1.2011.6.164.2.1.15.0.2"];
    public static TrapEntry Parse(IReadOnlyDictionary<string, string> values)
    {
        var trapOid = Exact("1.3.6.1.6.3.1.1.4.1.0"); var display = Names.TryGetValue(trapOid, out var name) ? $"{trapOid}:{name}" : trapOid;
        var levelText = Prefix("1.3.6.1.4.1.2011.6.164.1.1.2.100.1.3."); var level = levelText switch { "1" => AlarmLevel.Critical, "2" => AlarmLevel.Major, "3" => AlarmLevel.Minor, "4" => AlarmLevel.Warning, _ => AlarmLevel.Normal };
        return new TrapEntry(DateTime.Now, display, Exact("1.3.6.1.4.1.2011.6.164.1.1.2.2.0"), Prefix("1.3.6.1.4.1.2011.6.164.1.1.2.100.1.2."), level,
            Prefix("1.3.6.1.4.1.2011.6.164.1.34.1.1.2."), Prefix("1.3.6.1.4.1.2011.6.164.1.18.1.1.3."), Prefix("1.3.6.1.4.1.2011.6.164.1.34.1.1.3."), ResumeOids.Contains(trapOid));
        string Exact(string oid) => values.TryGetValue(oid, out var value) ? value : "";
        string Prefix(string prefix) => values.FirstOrDefault(v => v.Key.StartsWith(prefix, StringComparison.Ordinal)).Value ?? "";
    }
}
