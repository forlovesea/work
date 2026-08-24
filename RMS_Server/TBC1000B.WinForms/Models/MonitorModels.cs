namespace TBC1000B.WinForms.Models;

public enum ConnectionState { Disconnected, Connecting, Connected }
public enum AlarmLevel { Normal, Warning, Minor, Major, Critical }

public sealed class ModuleState
{
    public int Number { get; init; }
    public string RowIndex { get; set; } = "";
    public string SoftwareVersion { get; set; } = "-";
    public string EquipmentId { get; set; } = "-";
    public string Model { get; set; } = "-";
    public string Barcode { get; set; } = "-";
    public double? Voltage { get; set; }
    public double? Current { get; set; }
    public string Status { get; set; } = "-";
    public int? Soc { get; set; }
    public int? Soh { get; set; }
    public AlarmLevel Alarm { get; set; }
    public bool Connected { get; set; }
    public double?[] CellVoltages { get; } = new double?[15];
    public double?[] CellTemperatures { get; } = new double?[15];
}

public sealed record TrapEntry(DateTime Time, string Oid, string OrdinalNumber,
    string Alarm, AlarmLevel Level, string EquipmentId, string EquipmentName, string FatherEquipment, bool IsResume = false);

public sealed record FaultEntry(string Fault, int ModuleNo, int CellNo, double? Voltage, double? Temperature);
public sealed record ActiveAlarmEntry(string Text, AlarmLevel Level, string Time, int? ModuleNo, string EquipmentRow);

public sealed class MonitorSnapshot
{
    public List<ModuleState> Modules { get; } = Enumerable.Range(1, 10)
        .Select(n => new ModuleState { Number = n }).ToList();
    public List<TrapEntry> Traps { get; } = [];
    public List<FaultEntry> Faults { get; } = [];
    public List<ActiveAlarmEntry> ActiveAlarms { get; } = [];
    public ConnectionState Connection { get; set; }
    public DateTime? UpdatedAt { get; set; }
    public string? LastError { get; set; }
    public int ConsecutiveFailures { get; set; }
    public int TotalFailures { get; set; }
    public Dictionary<string, string> RawValues { get; } = new(StringComparer.Ordinal);
}
