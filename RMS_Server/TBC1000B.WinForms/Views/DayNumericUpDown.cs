using System.Globalization;

namespace TBC1000B.WinForms.Views;

internal sealed class DayNumericUpDown : NumericUpDown
{
    protected override void UpdateEditText()
    {
        if (UserEdit)
        {
            var input = Text.Trim();
            if (input.EndsWith("일", StringComparison.Ordinal)) input = input[..^1].TrimEnd();
            UserEdit = false;
            if (decimal.TryParse(input, NumberStyles.Integer, CultureInfo.CurrentCulture, out var days))
                Value = Math.Clamp(days, Minimum, Maximum);
        }
        ChangingText = true;
        Text = Value.ToString("0", CultureInfo.CurrentCulture) + "일";
    }

    protected override void ValidateEditText() => UpdateEditText();
    public override void UpButton() { ValidateEditText(); base.UpButton(); }
    public override void DownButton() { ValidateEditText(); base.DownButton(); }
}
