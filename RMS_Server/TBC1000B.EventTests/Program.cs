using TBC1000B.WinForms.Services;
using TBC1000B.WinForms.Models;
using TBC1000B.WinForms.Views;

internal static class Program
{
    private static int _checks;
    private static void Check(bool value, string description) { if (!value) throw new Exception(description); _checks++; }
    private static void Reject(Action action) { try { action(); } catch (ArgumentException) { _checks++; return; } throw new Exception("Expected validation failure"); }

    [STAThread]
    private static void Main(string[] args)
    {
        var folder = Path.Combine(Path.GetTempPath(), "TBC1000B-events-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(folder);
        var time = new DateTime(2026, 10, 25, 10, 0, 0);
        BatteryEventSample Sample(decimal amps, double minutes, int soc = 80) => new(time.AddMinutes(minutes), "Test rack", amps, 100m, 0.5m, soc);
        var recorder = new ChargeDischargeRecordService(folder);
        Check(recorder.Options == new ChargeDischargeRecordOptions(true, 50m, 10, true, 50m, 5), "Requested defaults enabled");
        var defaultRecorder = new ChargeDischargeRecordService(Path.Combine(folder, "defaults"));
        defaultRecorder.Observe(Sample(-49.9m, 0)); Check(!File.Exists(defaultRecorder.FilePath), "Default discharge below 50 percent waits");
        defaultRecorder.Observe(Sample(-50m, 1)); defaultRecorder.Observe(Sample(-50m, 6)); defaultRecorder.Observe(Sample(0, 7));
        Check(File.ReadAllLines(defaultRecorder.FilePath).Length == 4, "Default discharge starts at 50 percent and records at 5 minutes");
        defaultRecorder.Observe(Sample(50m, 8)); defaultRecorder.Observe(Sample(50m, 13));
        Check(File.ReadAllLines(defaultRecorder.FilePath).Length == 5, "Default charge waits beyond 5 minutes");
        defaultRecorder.Observe(Sample(50m, 18));
        Check(File.ReadAllLines(defaultRecorder.FilePath).Length == 6, "Default charge interval 10 minutes");
        var limited = new ChargeDischargeRecordService(Path.Combine(folder, "limited"));
        limited.Observe(Sample(50m, 0) with { ChargeLimitC = 0.4m });
        Check(!File.Exists(limited.FilePath) && limited.Status.Contains("보류"), "Default charge respects device cap");
        var options = new ChargeDischargeRecordOptions(true, 0.1m, 5, true, 10m, 5);
        Reject(() => recorder.Configure(options with { DischargeThresholdPercent = 0 }, Sample(0, 0)));
        Reject(() => recorder.Configure(options with { DischargeThresholdPercent = 91 }, Sample(0, 0)));
        Reject(() => recorder.Configure(options with { ChargeThresholdAmps = 50.1m }, Sample(0, 0)));
        Reject(() => recorder.Configure(options with { ChargeThresholdAmps = 0.01m }, Sample(0, 0)));
        Reject(() => recorder.Configure(options with { ChargeIntervalMinutes = 31 }, Sample(0, 0)));
        Reject(() => recorder.Configure(options with { ChargeIntervalMinutes = 6 }, Sample(0, 0)));
        Reject(() => recorder.Configure(options, null));
        recorder.Configure(options, Sample(0, 0));
        recorder.Observe(Sample(-9.9m, 0)); Check(!File.Exists(recorder.FilePath), "Below threshold must not start");
        recorder.Observe(Sample(-10m, 1));
        Check(File.ReadAllLines(recorder.FilePath).Length == 2, "Inclusive discharge start");
        recorder.Observe(Sample(-10m, 1)); recorder.Observe(Sample(-2m, 5));
        Check(File.ReadAllLines(recorder.FilePath).Length == 2, "No duplicate or early interval; below threshold is not end");
        recorder.Observe(Sample(-2m, 6, 70)); recorder.Observe(Sample(0, 7, 69));
        var rows = File.ReadAllLines(recorder.FilePath);
        Check(rows.Length == 4 && rows[2].Contains("\"인터벌\"") && rows[2].Contains("\"70\""), "Interval SOC");
        Check(rows[3].Contains("\"종료\"") && rows[3].Contains("\"69\"") && rows[3].Contains("전류 0A"), "Zero end and SOC");
        recorder.Observe(Sample(0.1m, 8, 69)); recorder.Observe(Sample(0.1m, 13, 71)); recorder.Observe(Sample(0, 14, 72));
        rows = File.ReadAllLines(recorder.FilePath);
        Check(rows.Length == 7 && rows[4].Contains("\"충전\"") && rows[6].Contains("\"72\""), "Charge start/interval/end");
        recorder.Observe(Sample(-20, 15)); recorder.Observe((BatteryEventSample?)null);
        rows = File.ReadAllLines(recorder.FilePath);
        Check(rows[^1].Contains("\"중단\"") && rows[^1].Contains("종료시각 미확정"), "Missing telemetry cannot be normal end");
        recorder.Observe(Sample(-20, 15)); Check(File.ReadAllLines(recorder.FilePath).Length == rows.Length, "No cached sample restart");
        recorder.Observe(Sample(-20, 16)); recorder.Observe(Sample(1, 17));
        rows = File.ReadAllLines(recorder.FilePath);
        Check(rows[^2].Contains("0A 미관측") && rows[^1].Contains("\"시작\""), "Direction reversal explicitly labelled");
        recorder.Configure(options with { ChargeEnabled = false, DischargeEnabled = false }, null);
        var stoppedCount = File.ReadAllLines(recorder.FilePath).Length;
        recorder.Observe(Sample(-20, 20)); Check(File.ReadAllLines(recorder.FilePath).Length == stoppedCount, "Disabled means no records");

        var longRecorder = new ChargeDischargeRecordService(Path.Combine(folder, "long"));
        longRecorder.Configure(options with { ChargeIntervalMinutes = 30 }, Sample(0, 0));
        longRecorder.Observe(Sample(1, 0)); longRecorder.Observe(Sample(1, 29));
        Check(File.ReadAllLines(longRecorder.FilePath).Length == 2, "30 minute interval waits");
        longRecorder.Observe(Sample(1, 30)); Check(File.ReadAllLines(longRecorder.FilePath).Length == 3, "30 minute interval records");
        longRecorder.Observe(Sample(1, 31) with { ChargeLimitC = null });
        Check(File.ReadAllLines(longRecorder.FilePath)[^1].Contains("\"중단\""), "Unavailable charge limit suspends recording");

        var failure = new ChargeDischargeRecordService(Path.Combine(folder, "failure"));
        failure.Configure(options, Sample(0, 0)); failure.Observe(Sample(1, 0));
        var errors = 0; failure.Error += (_, _) => errors++;
        using (var held = new FileStream(failure.FilePath, FileMode.Open, FileAccess.Read, FileShare.None)) failure.Observe(Sample(1, 5));
        Check(errors == 1 && !failure.Options.ChargeEnabled, "Locked file stops recording with explicit error");

        var snapshot = new MonitorSnapshot { Connection = ConnectionState.Connected, RackUpdatedAt = DateTime.Now };
        const string root = "1.3.6.1.4.1.2011.6.164.1";
        snapshot.RawValues[root + ".17.1.1.6.96"] = "-100"; snapshot.RawValues[root + ".17.1.1.7.96"] = "1000";
        snapshot.RawValues[root + ".17.1.1.8.96"] = "75"; snapshot.RawValues[root + ".17.2.1.13.96"] = "50";
        var sample = BatteryEventSample.Read(snapshot)!;
        Check(sample.CurrentAmps == -10 && sample.CapacityAh == 100 && sample.ChargeMaximumAmps == 50 && sample.Soc == 75, "Raw scaling");
        snapshot.RawValues[root + ".17.1.1.8.96"] = int.MaxValue.ToString(); Check(BatteryEventSample.Read(snapshot) is null, "Invalid sentinel rejected");
        Check(BatteryEventSample.ReadChargeMaximumAmps(snapshot) == 50, "Charge input cap independent of missing SOC");
        snapshot.RawValues[root + ".17.1.1.8.96"] = "75";
        snapshot.ConsecutiveFailures = 1; Check(BatteryEventSample.Read(snapshot) is null, "Failed poll rejects cached data"); snapshot.ConsecutiveFailures = 0;
        if (args.Contains("--ui"))
        {
            ApplicationConfiguration.Initialize();
            var operation = new OperationRecordService(folder);
            using var dialog = new OperationRecordDialog(operation, () => snapshot, new ChargeDischargeRecordService(folder));
            dialog.Show(); Application.DoEvents();
            IEnumerable<Control> All(Control parent) => parent.Controls.Cast<Control>().SelectMany(c => new[] { c }.Concat(All(c)));
            var controls = All(dialog).ToArray();
            var charge = controls.OfType<CheckBox>().Single(c => c.Text == "충전 이벤트 사용");
            var discharge = controls.OfType<CheckBox>().Single(c => c.Text == "방전 이벤트 사용");
            var chargeThreshold = controls.OfType<NumericUpDown>().Single(c => c.DecimalPlaces == 1);
            var dischargeThreshold = controls.OfType<NumericUpDown>().Single(c => c.Maximum == 90);
            Check(charge.Checked && discharge.Checked && chargeThreshold.Value == 50m && dischargeThreshold.Value == 50m,
                "UI defaults both enabled and thresholds 50A/50 percent");
            var eventIntervals = controls.OfType<ComboBox>().Where(c => c.Items.Count == 6).ToArray();
            Check(eventIntervals[0].SelectedIndex == 0 && eventIntervals[1].SelectedIndex == 1, "UI defaults discharge 5 / charge 10 minutes");
            charge.Checked = discharge.Checked = false;
            Check(!chargeThreshold.Enabled && !dischargeThreshold.Enabled, "Unchecked fields disabled");
            charge.Checked = discharge.Checked = true;
            Check(chargeThreshold.Enabled && dischargeThreshold.Enabled && chargeThreshold.Maximum == 50, "Checked fields enabled with calculated maximum");
            chargeThreshold.Value = 12.3m;
            snapshot.RawValues.Remove(root + ".17.1.1.8.96");
            var refresh = typeof(OperationRecordDialog).GetMethod("RefreshLimits", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)!;
            refresh.Invoke(dialog, null);
            Check(chargeThreshold.Enabled && chargeThreshold.Value == 12.3m && chargeThreshold.Maximum == 50, "Missing SOC keeps checked charge input editable");
            snapshot.RawValues.Remove(root + ".17.2.1.13.96"); refresh.Invoke(dialog, null);
            Check(chargeThreshold.Enabled && chargeThreshold.Value == 12.3m && chargeThreshold.Maximum == 50, "Temporary cap loss preserves draft and last cap");
            charge.Checked = false; Check(!chargeThreshold.Enabled, "Uncheck disables input"); charge.Checked = true;
            Check(charge.Visible && charge.Height > 0 && charge.Bottom <= charge.Parent!.ClientSize.Height, "Charge row fully visible");
            using var bitmap = new Bitmap(dialog.Width, dialog.Height); dialog.DrawToBitmap(bitmap, new Rectangle(0, 0, dialog.Width, dialog.Height));
            bitmap.Save(Path.Combine(folder, "event-dialog.png")); dialog.Close();
            Console.WriteLine("UI image: " + Path.Combine(folder, "event-dialog.png"));
            using var noData = new OperationRecordDialog(operation, () => null, new ChargeDischargeRecordService(folder));
            var noDataControls = All(noData).ToArray();
            var noDataCharge = noDataControls.OfType<CheckBox>().Single(c => c.Text == "충전 이벤트 사용");
            var noDataThreshold = noDataControls.OfType<NumericUpDown>().Single(c => c.DecimalPlaces == 1);
            noDataCharge.Checked = true; noDataThreshold.Value = 1.2m; refresh.Invoke(noData, null);
            Check(noDataThreshold.Enabled && noDataThreshold.Value == 1.2m, "No telemetry allows draft input without reset");
            Check(noDataControls.OfType<ComboBox>().Where(c => c.Items.Count == 6).All(c => c.Enabled), "Default intervals editable without telemetry");
        }
        Console.WriteLine($"PASS: {_checks} event recording checks. Artifacts: {folder}");
    }
}
