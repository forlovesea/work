using System.Globalization;

namespace TBC1000B.WinForms.Services;

internal static class SnmpValueValidation
{
    // V3.2.4 uses the signed Integer32 maximum as the device's unavailable value.
    public static bool IsUnavailable(string text) =>
        long.TryParse(text, NumberStyles.Integer, CultureInfo.InvariantCulture, out var value)
        && value == int.MaxValue;

    public static bool TryInteger(string text, out int value) =>
        int.TryParse(text, NumberStyles.Integer, CultureInfo.InvariantCulture, out value)
        && value != int.MaxValue;
}
