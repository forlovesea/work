using System.Globalization;
using System.Text;
using TBC1000B.WinForms.Models;

namespace TBC1000B.WinForms.Services;

public sealed record ChargeDischargeRecordOptions(bool ChargeEnabled = true, decimal ChargeThresholdAmps = 50m,
    int ChargeIntervalMinutes = 10, bool DischargeEnabled = true, decimal DischargeThresholdPercent = 50m,
    int DischargeIntervalMinutes = 5);

public sealed record BatteryEventSample(DateTime Time, string SystemName, decimal CurrentAmps,
    decimal CapacityAh, decimal? ChargeLimitC, int Soc)
{
    public decimal ChargeMaximumAmps => decimal.Floor(CapacityAh * (ChargeLimitC ?? 0) * 10) / 10;
    // Editing the threshold needs capacity and C only, not current/SOC telemetry.
    public static decimal? ReadChargeMaximumAmps(MonitorSnapshot snapshot)
    {
        const string root = "1.3.6.1.4.1.2011.6.164.1";
        lock (snapshot)
        {
            if (snapshot.Connection != ConnectionState.Connected) return null;
            if (!snapshot.RawValues.TryGetValue(root + ".17.1.1.7.96", out var capacityText)
                || !SnmpValueValidation.TryInteger(capacityText, out var capacity) || capacity <= 0
                || !snapshot.RawValues.TryGetValue(root + ".17.2.1.13.96", out var limitText)
                || !SnmpValueValidation.TryInteger(limitText, out var limit) || limit <= 0) return null;
            return decimal.Floor((capacity / 10m) * (limit / 100m) * 10) / 10;
        }
    }
    public static BatteryEventSample? Read(MonitorSnapshot snapshot)
    {
        const string root = "1.3.6.1.4.1.2011.6.164.1";
        lock (snapshot)
        {
            if (snapshot.Connection != ConnectionState.Connected || snapshot.ConsecutiveFailures != 0 || snapshot.RackUpdatedAt is not { } at) return null;
            int? Read(string suffix) => snapshot.RawValues.TryGetValue(root + suffix, out var text)
                && SnmpValueValidation.TryInteger(text, out var n) ? n : null;
            var current = Read(".17.1.1.6.96"); var capacity = Read(".17.1.1.7.96");
            var soc = Read(".17.1.1.8.96"); var limit = Read(".17.2.1.13.96");
            if (current is null || capacity is not > 0 || soc is null or < 0 or > 100) return null;
            return new(at, snapshot.SystemName, current.Value / 10m, capacity.Value / 10m,
                limit is > 0 ? limit.Value / 100m : null, soc.Value);
        }
    }
}

/// <summary>Consumes successful SNMP samples; never treats cached data as a new observation.</summary>
public sealed class ChargeDischargeRecordService
{
    private readonly object _gate = new();
    private readonly string _directory;
    private ActiveEvent? _charge, _discharge;
    private DateTime? _lastTime;
    private bool _hasSample, _chargeBlocked;
    private bool _initializeChargeThreshold = true;
    public bool IsMonitoring { get; private set; } = true;
    public ChargeDischargeRecordOptions Options { get; private set; } = new();
    public string Status { get; private set; } = "충방전 이벤트 기본 사용 · 장비 데이터 수신 대기";
    public string FilePath => Path.Combine(_directory, "충방전 이벤트 기록.csv");
    public event EventHandler<string>? Error;
    public string StateText
    {
        get
        {
            lock (_gate)
            {
                if (!IsMonitoring) return "중지";
                if (!Options.ChargeEnabled && !Options.DischargeEnabled) return "미사용";
                if (!_hasSample) return "데이터 대기";
                if (_discharge is not null) return "방전 기록 중";
                if (_charge is not null) return "충전 기록 중";
                return _chargeBlocked ? (Options.DischargeEnabled ? "충전 보류 · 방전 감시" : "충전 보류") : "감시 중";
            }
        }
    }
    private sealed record ActiveEvent(string Id, string Direction, BatteryEventSample Start, BatteryEventSample Last,
        DateTime NextAt, decimal Threshold, int Interval);

    public ChargeDischargeRecordService(string directory) => _directory = directory;

    public void Configure(ChargeDischargeRecordOptions options, BatteryEventSample? sample)
    {
        if (options.DischargeThresholdPercent is < 1 or > 90) throw new ArgumentException("방전 임계값은 1~90%입니다.");
        if (options.ChargeThresholdAmps < 0.1m || options.ChargeThresholdAmps * 10 != decimal.Truncate(options.ChargeThresholdAmps * 10))
            throw new ArgumentException("충전 임계값은 0.1A 이상, 0.1A 단위입니다.");
        foreach (var interval in new[] { options.ChargeIntervalMinutes, options.DischargeIntervalMinutes })
            if (interval < 5 || interval > 30 || interval % 5 != 0) throw new ArgumentException("이벤트 기록 간격은 5분 단위, 5~30분입니다.");
        if ((options.ChargeEnabled || options.DischargeEnabled) && sample is null) throw new ArgumentException("최신 전류·총용량·SOC 수신 후 설정하세요.");
        if (options.ChargeEnabled && options.ChargeThresholdAmps > sample!.ChargeMaximumAmps)
            throw new ArgumentException("충전 임계값이 총용량 × 충전전류제한(C) 상한을 초과합니다.");
        lock (_gate)
        {
            // Explicit settings take precedence over first-connection defaults.
            _initializeChargeThreshold = false;
            if (options == Options) return;
            Interrupt("설정 변경", DateTime.Now);
            Options = options; _lastTime = null;
            if (!options.ChargeEnabled && !options.DischargeEnabled) IsMonitoring = false;
            _hasSample = false; _chargeBlocked = false;
            Status = !IsMonitoring ? "이벤트 기록 중지 · 시작 버튼으로 재개" : options.ChargeEnabled || options.DischargeEnabled ? "충방전 이벤트 감시 중" : "충방전 이벤트 기록 미사용";
        }
    }

    public void Start(ChargeDischargeRecordOptions options, BatteryEventSample? sample)
    {
        if (!options.ChargeEnabled && !options.DischargeEnabled) throw new ArgumentException("충전 또는 방전 이벤트를 하나 이상 선택하세요.");
        lock (_gate)
        {
            Configure(options, sample);
            if (IsMonitoring) return;
            IsMonitoring = true; _lastTime = null; _hasSample = false; _chargeBlocked = false;
            Status = "충방전 이벤트 감시 중";
        }
        Observe(sample);
    }

    public void Observe(MonitorSnapshot snapshot) => Observe(BatteryEventSample.Read(snapshot));
    public void Observe(BatteryEventSample? sample)
    {
        string? error = null;
        lock (_gate)
        {
            if (!IsMonitoring || (!Options.ChargeEnabled && !Options.DischargeEnabled)) return;
            try
            {
                if (sample is null) { Interrupt("통신 또는 필수 측정값 누락", DateTime.Now); _hasSample = false; Status = "최신 전류·용량·SOC 수신 대기"; return; }
                if (_lastTime is { } previous && sample.Time <= previous) return;
                _lastTime = sample.Time;
                _hasSample = true;
                if (_initializeChargeThreshold && sample.ChargeMaximumAmps >= 0.1m)
                {
                    // The initial 50A must be reachable within the device's C-rate cap.
                    Options = Options with { ChargeThresholdAmps = Math.Min(Options.ChargeThresholdAmps, sample.ChargeMaximumAmps) };
                    _initializeChargeThreshold = false;
                }
                if (_charge is not null && sample.CurrentAmps <= 0) Finish(ref _charge, sample);
                if (_discharge is not null && sample.CurrentAmps >= 0) Finish(ref _discharge, sample);
                var chargeAllowed = Options.ChargeEnabled && Options.ChargeThresholdAmps <= sample.ChargeMaximumAmps;
                _chargeBlocked = Options.ChargeEnabled && !chargeAllowed;
                if (!chargeAllowed && _charge is not null) InterruptOne(ref _charge, "충전 임계값 상한 변경", sample.Time);
                Advance(ref _charge, chargeAllowed, sample.CurrentAmps, Options.ChargeThresholdAmps,
                    Options.ChargeIntervalMinutes, "충전", sample);
                Advance(ref _discharge, Options.DischargeEnabled, -sample.CurrentAmps,
                    sample.CapacityAh * Options.DischargeThresholdPercent / 100, Options.DischargeIntervalMinutes, "방전", sample);
                Status = Options.ChargeEnabled && !chargeAllowed ? "충전 감시 보류: 임계값 상한 확인 후 재설정" : "충방전 이벤트 감시 중";
                if (_charge is not null) Status += " · 충전 진행";
                if (_discharge is not null) Status += " · 방전 진행";
            }
            catch (Exception ex)
            {
                IsMonitoring = false;
                _charge = _discharge = null;
                Status = "이벤트 저장 오류 · 감시 중지"; error = ex.Message;
            }
        }
        if (error is not null) Error?.Invoke(this, "충방전 이벤트 기록 실패: " + error);
    }

    private void Advance(ref ActiveEvent? active, bool enabled, decimal magnitude, decimal threshold,
        int interval, string direction, BatteryEventSample sample)
    {
        if (!enabled) return;
        if (active is null)
        {
            if (magnitude < threshold) return;
            var created = new ActiveEvent(Guid.NewGuid().ToString("N"), direction, sample, sample, sample.Time.AddMinutes(interval), threshold, interval);
            Write(created, "시작", sample, sample.Time, "임계전류 이상 감지"); active = created;
        }
        else
        {
            if (sample.Time >= active.NextAt)
            {
                Write(active, "인터벌", sample, sample.Time, "주기 기록");
                active = active with { NextAt = sample.Time.AddMinutes(active.Interval) };
            }
            active = active with { Last = sample };
        }
    }

    private void Finish(ref ActiveEvent? active, BatteryEventSample sample)
    {
        Write(active!, "종료", sample, sample.Time, sample.CurrentAmps == 0 ? "전류 0A" : "전류 방향 전환 (0A 미관측)"); active = null;
    }
    private void InterruptOne(ref ActiveEvent? active, string reason, DateTime at)
    {
        if (active is null) return;
        Write(active, "중단", active.Last, at, reason + " · 종료시각 미확정"); active = null;
    }
    private void Interrupt(string reason, DateTime at)
    {
        InterruptOne(ref _charge, reason, at); InterruptOne(ref _discharge, reason, at);
    }
    public void Stop(string reason = "사용자 중지")
    {
        string? error = null;
        lock (_gate)
        {
            if (!IsMonitoring) return;
            IsMonitoring = false;
            try { Interrupt(reason, DateTime.Now); }
            catch (Exception ex) { error = "이벤트 중단 기록 실패: " + ex.Message; }
            finally { _charge = _discharge = null; _hasSample = false; _lastTime = null; }
            Status = error is null ? "이벤트 기록 중지 · 시작 버튼으로 재개" : "이벤트 기록 중지 · 중단 행 저장 실패";
        }
        if (error is not null) Error?.Invoke(this, error);
    }

    private void Write(ActiveEvent active, string phase, BatteryEventSample sample, DateTime at, string reason)
    {
        Directory.CreateDirectory(_directory);
        // FileShare.Read permits Excel inspection but excludes concurrent writers.
        using var stream = new FileStream(FilePath, FileMode.OpenOrCreate, FileAccess.Write, FileShare.Read);
        var empty = stream.Length == 0; stream.Seek(0, SeekOrigin.End);
        using var writer = new StreamWriter(stream, new UTF8Encoding(true));
        if (empty) writer.WriteLine("이벤트ID,시스템,종류,기록구분,기록시각,측정시각,시작시각,전류[A],SOC[%],총용량[Ah],시작임계전류[A],인터벌[분],사유");
        string Time(DateTime t) => t.ToString("yyyy-MM-dd HH:mm:ss.fff", CultureInfo.InvariantCulture);
        object[] row = [active.Id, sample.SystemName, active.Direction, phase, Time(at), Time(sample.Time), Time(active.Start.Time),
            sample.CurrentAmps, sample.Soc, sample.CapacityAh, active.Threshold, active.Interval, reason];
        writer.WriteLine(string.Join(",", row.Select(Csv))); writer.Flush(); stream.Flush(true);
    }
    private static string Csv(object value)
    {
        var text = Convert.ToString(value, CultureInfo.InvariantCulture) ?? "";
        if (value is string && text.Length > 0 && "=+-@\t\r\n".Contains(text[0])) text = "'" + text;
        return "\"" + text.Replace("\"", "\"\"") + "\"";
    }
}
