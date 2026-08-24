using System.Globalization;
using System.Text.RegularExpressions;
using TBC1000B.WinForms.Models;

namespace TBC1000B.WinForms.Services;

public static class SnmpDataMapper
{
    private const string Root = "1.3.6.1.4.1.2011.6.164.1";
    public static void Apply(MonitorSnapshot snapshot, IReadOnlyDictionary<string, string> raw)
    {
        var rowToModule = new Dictionary<string, int>(); var infoRows = new Dictionary<string, ModuleState>();
        foreach (var item in raw.Where(x => x.Key.StartsWith(Root + ".18.1.1.2.", StringComparison.Ordinal)))
        {
            var row = Last(item.Key); if (!TryInt(raw, $"{Root}.18.1.1.4.{row}", out var number) || number is < 1 or > 10) continue;
            var module = snapshot.Modules[number - 1]; module.RowIndex = row; module.EquipmentId = item.Value; module.SoftwareVersion = Get(raw, $"{Root}.18.1.1.5.{row}"); module.Model = Get(raw, $"{Root}.18.1.1.12.{row}"); module.Barcode = Get(raw, $"{Root}.18.1.1.13.{row}"); module.Connected = true;
            rowToModule[row] = number; infoRows[row] = module;
        }
        foreach (var module in snapshot.Modules.Where(m => !rowToModule.ContainsValue(m.Number))) Reset(module);
        foreach (var item in raw.Where(x => x.Key.StartsWith(Root + ".18.2.1.", StringComparison.Ordinal)))
        {
            var parts = item.Key.Split('.'); if (parts.Length < 2 || !int.TryParse(parts[^2], out var column) || !infoRows.TryGetValue(parts[^1], out var module)) continue;
            if (!long.TryParse(item.Value, NumberStyles.Integer, CultureInfo.InvariantCulture, out var value) || value == int.MaxValue) continue;
            switch (column)
            {
                case 1: module.Voltage = value / 10d; break; case 2: module.Current = value / 10d; break;
                case 3: module.Status = StatusText((int)value); break; case 4: module.Soh = (int)value; break; case 52: module.Soc = (int)value; break;
                case >= 6 and <= 20: module.CellVoltages[column - 6] = Math.Round(value / 100d, 2); break;
                case >= 22 and <= 36: module.CellTemperatures[column - 22] = Math.Round(value / 10d, 1); break;
            }
        }
        snapshot.ActiveAlarms.Clear(); snapshot.Faults.Clear(); foreach (var module in snapshot.Modules) module.Alarm = AlarmLevel.Normal;
        var alarmRows = raw.Where(x => x.Key.StartsWith(Root + ".1.2.99.1.2.", StringComparison.Ordinal));
        foreach (var alarm in alarmRows)
        {
            var index = Last(alarm.Key); var equipmentRow = Get(raw, $"{Root}.1.2.99.1.10.{index}"); int? moduleNo = rowToModule.TryGetValue(equipmentRow, out var found) ? found : null;
            var level = TryInt(raw, $"{Root}.1.2.99.1.3.{index}", out var rawLevel) ? Level(rawLevel) : AlarmLevel.Normal; var time = Get(raw, $"{Root}.1.2.99.1.5.{index}");
            snapshot.ActiveAlarms.Add(new ActiveAlarmEntry(alarm.Value, level, time, moduleNo, equipmentRow)); if (moduleNo is { } no && level > snapshot.Modules[no - 1].Alarm) snapshot.Modules[no - 1].Alarm = level;
            if (!IsFault(alarm.Value)) continue; var cellMatch = Regex.Match(alarm.Value, @"cell\s*(\d+)\s*fault", RegexOptions.IgnoreCase); var cell = cellMatch.Success ? int.Parse(cellMatch.Groups[1].Value) : 0; var faultModule = moduleNo ?? 0; double? voltage = null, temperature = null;
            if (moduleNo is { } faultNo && cell is >= 1 and <= 15) { voltage = snapshot.Modules[faultNo - 1].CellVoltages[cell - 1]; temperature = snapshot.Modules[faultNo - 1].CellTemperatures[cell - 1]; }
            snapshot.Faults.Add(new FaultEntry(alarm.Value, faultModule, cell, voltage, temperature));
        }
    }
    private static void Reset(ModuleState m) { m.RowIndex = ""; m.Connected = false; m.Voltage = null; m.Current = null; m.Status = "-"; m.Soc = null; m.Soh = null; m.Alarm = AlarmLevel.Normal; Array.Clear(m.CellVoltages); Array.Clear(m.CellTemperatures); }
    private static string StatusText(int value) => value switch { 0 => "Online", 1 => "Offline", 2 => "Sleep", 3 => "Disconnect", 4 => "충전중", 5 => "방전중", 6 => "Standby", _ => "Unknown" };
    private static AlarmLevel Level(int value) => value switch { 1 => AlarmLevel.Critical, 2 => AlarmLevel.Major, 3 => AlarmLevel.Minor, 4 => AlarmLevel.Warning, _ => AlarmLevel.Normal };
    private static bool IsFault(string text) => text.Equals("Board hardware fault", StringComparison.OrdinalIgnoreCase) || Regex.IsMatch(text, @"^Cell\s*(?:[1-9]|1[0-5])\s*Fault$", RegexOptions.IgnoreCase);
    private static string Last(string oid) => oid[(oid.LastIndexOf('.') + 1)..];
    private static string Get(IReadOnlyDictionary<string, string> raw, string oid) => raw.TryGetValue(oid, out var value) ? value : "-";
    private static bool TryInt(IReadOnlyDictionary<string, string> raw, string oid, out int value) => int.TryParse(Get(raw, oid), NumberStyles.Integer, CultureInfo.InvariantCulture, out value);
}
