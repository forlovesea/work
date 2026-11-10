using TBC1000B.WinForms.Models;
using TBC1000B.WinForms.Snmp;

namespace TBC1000B.WinForms.Services;

public static class DeviceFeatureSupport
{
    public const string SocEnableOid = "1.3.6.1.4.1.2011.6.164.1.17.2.1.29.96";
    public const string SocValueOid = "1.3.6.1.4.1.2011.6.164.1.17.2.1.30.96";
    public const string EpoPrepareOid = "1.3.6.1.4.1.2011.6.164.1.2.2.1.1.11.1";
    public const string EpoTableRoot = "1.3.6.1.4.1.2011.6.164.1.2.2.1";
    public const string EpoRoot = "1.3.6.1.4.1.2011.6.164.1.18.3.1.2";

    public static bool SocSupported(MonitorSnapshot? snapshot) =>
        HasValue(snapshot, SocEnableOid) && HasValue(snapshot, SocValueOid);

    public static bool EpoSupported(MonitorSnapshot? snapshot, ModuleState module) =>
        snapshot?.Connection == ConnectionState.Connected && snapshot.EpoSupported
        && !string.IsNullOrWhiteSpace(module.RowIndex);

    public static bool IsValidEpoPrepareResponse(SnmpVariable value) =>
        value.Oid == EpoPrepareOid && value.Type == SnmpDataType.Integer
        && SnmpValueValidation.TryInteger(value.DisplayValue, out _);

    private static bool HasValue(MonitorSnapshot? snapshot, string oid) =>
        snapshot?.Connection == ConnectionState.Connected
        && snapshot.RawValues.TryGetValue(oid, out var text)
        && SnmpValueValidation.TryInteger(text, out _);
}
