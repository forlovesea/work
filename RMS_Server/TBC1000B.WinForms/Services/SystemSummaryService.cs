using System.Globalization;
using TBC1000B.WinForms.Models;

namespace TBC1000B.WinForms.Services;

public sealed record SystemSummary(IReadOnlyDictionary<string, string> Values, string Title);

public static class SystemSummaryService
{
    private const string Root = "1.3.6.1.4.1.2011.6.164.1";

    public static SystemSummary Create(MonitorSnapshot snapshot)
    {
        var active = snapshot.Modules.Where(m => m.Connected && m.Status is "충전중" or "방전중" or "Standby").ToArray();
        var volts = active.Where(m => m.Voltage.HasValue).Select(m => m.Voltage!.Value).ToArray();
        var temperatures = active.SelectMany(m => m.CellTemperatures).Where(v => v.HasValue).Select(v => v!.Value).ToArray();
        var values = new Dictionary<string, string>(StringComparer.Ordinal)
        {
            ["Rack 전압[V]"] = Scaled(snapshot, $"{Root}.17.1.1.5.96", 10, "0.0"),
            ["SOC 충전율[%]"] = Raw(snapshot, $"{Root}.17.1.1.8.96"),
            ["Max 전압[V]"] = Aggregate(volts, Enumerable.Max),
            ["Min 전압[V]"] = Aggregate(volts, Enumerable.Min),
            ["Avg 전압[V]"] = Aggregate(volts, Enumerable.Average),
            ["Rack 전류[A]"] = Scaled(snapshot, $"{Root}.17.1.1.6.96", 10, "0.0"),
            ["방전 횟수"] = Raw(snapshot, $"{Root}.17.1.1.23.96"),
            ["Max 온도[℃]"] = Aggregate(temperatures, Enumerable.Max),
            ["Min 온도[℃]"] = Aggregate(temperatures, Enumerable.Min),
            ["Avg 온도[℃]"] = Aggregate(temperatures, Enumerable.Average),
            ["과전압 충전차단"] = AlarmState(snapshot, "overcharge protection", "overcharge voltage protection"),
            ["고온 충전차단"] = AlarmState(snapshot, "charging high temperature protection", "charge high temperature protection", "high temperature protection"),
            ["과전류 충전차단"] = AlarmState(snapshot, "charging overcurrent protection", "charge overcurrent protection"),
            ["차단기 OFF"] = AlarmState(snapshot, "battery fuse broken"),
            ["충전전류제한[C]"] = Scaled(snapshot, $"{Root}.17.2.1.13.96", 100, "0.00"),
            ["SOC충전제한[%]"] = Raw(snapshot, $"{Root}.17.2.1.30.96")
        };
        var capacity = Scaled(snapshot, $"{Root}.17.1.1.7.96", 10, "0");
        var soh = Raw(snapshot, $"{Root}.17.1.1.13.96");
        var title = capacity == "-" || soh == "-" ? "시스템 요약 정보" : $"시스템 요약 정보 (Rack 전체용량: {capacity}Ah, SOH: {soh}%)";
        return new SystemSummary(values, title);
    }

    private static string Raw(MonitorSnapshot snapshot, string oid) => snapshot.RawValues.TryGetValue(oid, out var value) && SnmpValueValidation.TryInteger(value, out var number) ? number.ToString(CultureInfo.InvariantCulture) : "-";
    private static string Scaled(MonitorSnapshot snapshot, string oid, double divisor, string format) =>
        SnmpValueValidation.TryInteger(Raw(snapshot, oid), out var value)
            ? (value / divisor).ToString(format, CultureInfo.InvariantCulture) : "-";
    private static string Aggregate(double[] values, Func<IEnumerable<double>, double> aggregate) =>
        values.Length == 0 ? "-" : aggregate(values).ToString("0.0", CultureInfo.InvariantCulture);
    private static string AlarmState(MonitorSnapshot snapshot, params string[] keywords) =>
        snapshot.ActiveAlarms.Any(alarm => keywords.Any(keyword => alarm.Text.Contains(keyword, StringComparison.OrdinalIgnoreCase))) ? "비정상" : "정상";
}
