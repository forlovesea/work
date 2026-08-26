namespace TBC1000B.WinForms.Models;

public sealed class Profile
{
    public required string FilePath { get; set; }
    public string Site { get; set; } = "";
    public string SystemName { get; set; } = "";
    public string Equipment { get; set; } = "";
    public string Manager { get; set; } = "";
    public string Maker { get; set; } = "";
    public string Model { get; set; } = "";
    public string Serial { get; set; } = "";
    public string Address { get; set; } = "60.22.0.0";
    public int Port { get; set; } = 161;
    public string GetCommunity { get; set; } = "sktlfp48r";
    public string SetCommunity { get; set; } = "sktlfp48w";
    public string TrapCommunity { get; set; } = "sktlfp48r";
    public int TrapPort { get; set; } = 162;
    public int LocalTrapPort { get; set; }
    public int[] ModuleOrder { get; set; } = Enumerable.Range(1, 10).ToArray();
    public Dictionary<int, string> ModuleBarcodes { get; } = [];
    public Dictionary<int, string> EpoCutoffTimes { get; } = [];
    public int AlarmVolume { get; set; }
    public Dictionary<int, bool> AlarmLevels { get; } = new() { [1] = true, [2] = true, [3] = true, [4] = false, [255] = false };
}
