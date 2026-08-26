using System.Text;
using System.Text.RegularExpressions;
using TBC1000B.WinForms.Models;

namespace TBC1000B.WinForms.Services;

public sealed class ProfileStore
{
    public string DirectoryPath { get; }
    public ProfileStore(string directoryPath) { DirectoryPath = directoryPath; Directory.CreateDirectory(directoryPath); }

    public IReadOnlyList<string> ListProfiles() => Directory.EnumerateFiles(DirectoryPath, "*.ini")
        .OrderBy(Path.GetFileName, StringComparer.CurrentCultureIgnoreCase).ToArray();

    public Profile Load(string path)
    {
        var values = Parse(path);
        var profile = new Profile { FilePath = path };
        profile.Site = Get(values, "General/site"); profile.SystemName = Get(values, "General/system");
        profile.Equipment = Get(values, "General/equip"); profile.Manager = Get(values, "General/manager"); profile.Maker = Get(values, "General/maker");
        profile.Model = Get(values, "General/model"); profile.Serial = Get(values, "General/serial");
        profile.Address = Get(values, "General/ip", profile.Address); profile.Port = GetInt(values, "General/port", 161);
        profile.GetCommunity = Get(values, "General/get_comm", profile.GetCommunity); profile.SetCommunity = Get(values, "General/set_comm", profile.SetCommunity);
        profile.TrapCommunity = Get(values, "General/trap_comm", profile.TrapCommunity); profile.TrapPort = GetInt(values, "General/trap_port", 162); profile.LocalTrapPort = GetInt(values, "General/local_trap_port", 0);
        profile.AlarmVolume = GetInt(values, "alarm/volume", 0);
        foreach (var key in profile.AlarmLevels.Keys.ToArray()) profile.AlarmLevels[key] = GetBool(values, $"alarm/level\\{key}", profile.AlarmLevels[key]);
        var orderText = Get(values, "General/module_order");
        if (orderText.Length > 0) { var order = orderText.Split(',').Select(token => int.TryParse(token.Trim(), out var n) && n is >= 1 and <= 10 ? n : 0).Take(10).ToList(); while (order.Count < 10) order.Add(0); profile.ModuleOrder = order.ToArray(); }
        for (var module = 1; module <= 10; module++) { var barcode = Get(values, $"module_barcodes/{module}"); if (barcode.Length > 0) profile.ModuleBarcodes[module] = barcode; }
        for (var module = 1; module <= 10; module++) { var cutoffTime = Get(values, $"epo/cutoff_time\\{module}"); if (cutoffTime.Length > 0) profile.EpoCutoffTimes[module] = cutoffTime; }
        return profile;
    }

    public Profile Create(string site, string systemName)
    {
        var file = SafeName($"{site}_{systemName}") + ".ini";
        var profile = new Profile { FilePath = Path.Combine(DirectoryPath, file), Site = site, SystemName = systemName };
        Save(profile); return profile;
    }

    public void Save(Profile profile)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(profile.FilePath)!);
        var text = new StringBuilder("[General]\r\n");
        Pair("site", profile.Site); Pair("system", profile.SystemName); Pair("equip", profile.Equipment); Pair("manager", profile.Manager); Pair("maker", profile.Maker); Pair("model", profile.Model); Pair("serial", profile.Serial);
        Pair("ip", profile.Address); Pair("port", profile.Port); Pair("get_comm", profile.GetCommunity); Pair("set_comm", profile.SetCommunity); Pair("trap_comm", profile.TrapCommunity); Pair("trap_port", profile.TrapPort);
        if (profile.LocalTrapPort > 0) Pair("local_trap_port", profile.LocalTrapPort);
        Pair("module_order", string.Join(", ", profile.ModuleOrder));
        text.Append("\r\n[module_barcodes]\r\n"); foreach (var item in profile.ModuleBarcodes.OrderBy(item => item.Key)) Pair(item.Key.ToString(), item.Value);
        text.Append("\r\n[epo]\r\n"); foreach (var item in profile.EpoCutoffTimes.OrderBy(item => item.Key)) Pair($"cutoff_time\\{item.Key}", item.Value);
        text.Append("\r\n[alarm]\r\n"); Pair("volume", profile.AlarmVolume); foreach (var item in profile.AlarmLevels) Pair($"level\\{item.Key}", item.Value ? "true" : "false");
        File.WriteAllText(profile.FilePath, text.ToString(), new UTF8Encoding(false));
        void Pair(string key, object? value) => text.Append(key).Append('=').Append(value).Append("\r\n");
    }

    public void Delete(string path) { if (File.Exists(path)) File.Delete(path); }
    private static string SafeName(string value) => Regex.Replace(value.Trim(), @"[^\p{L}\p{N}_-]", "_");

    private static Dictionary<string, string> Parse(string path)
    {
        var result = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase); var section = "General";
        if (!File.Exists(path)) return result;
        foreach (var raw in File.ReadLines(path)) { var line = raw.Trim(); if (line.Length == 0 || line.StartsWith(';') || line.StartsWith('#')) continue; if (line.StartsWith('[') && line.EndsWith(']')) { section = line[1..^1]; continue; } var index = line.IndexOf('='); if (index > 0) result[$"{section}/{line[..index].Trim()}"] = line[(index + 1)..].Trim(); }
        return result;
    }
    private static string Get(IReadOnlyDictionary<string, string> map, string key, string fallback = "") => map.TryGetValue(key, out var value) ? value : fallback;
    private static int GetInt(IReadOnlyDictionary<string, string> map, string key, int fallback) => int.TryParse(Get(map, key), out var value) ? value : fallback;
    private static bool GetBool(IReadOnlyDictionary<string, string> map, string key, bool fallback) => bool.TryParse(Get(map, key), out var value) ? value : fallback;
}
