using System.Globalization;
using TBC1000B.WinForms.Models;

namespace TBC1000B.WinForms.Services;

public sealed record OperationRecordOptions(int IntervalMinutes, int DurationDays, IReadOnlySet<string> Fields);

public sealed class OperationRecordService : IAsyncDisposable
{
    public static readonly (string Key, string Label, string[] Headers)[] FieldSpecs = [
        ("equipment", "장비 기본정보", ["Row Index", "Equip ID", "모델", "Barcode"]),
        ("voltage", "모듈 전압", ["모듈 전압[V]"]), ("current", "모듈 전류", ["모듈 전류[A]"]),
        ("soc_soh", "SOC / SOH", ["SOC[%]", "SOH[%]"]), ("status", "통신상태", ["상태", "통신상태"]),
        ("alarm", "경보", ["경보"]), ("cell_summary", "셀 전압 Max / Min", ["셀 전압 Max[V]", "셀 전압 Min[V]"]),
        ("cell_detail", "셀 전압 상세 (01~15)", Enumerable.Range(1, 15).Select(n => $"Cell {n:00}[V]").ToArray()),
        ("temp_summary", "셀 온도 Max / Min", ["셀 온도 Max[℃]", "셀 온도 Min[℃]"]),
        ("temp_detail", "셀 온도 상세 (01~15)", Enumerable.Range(1, 15).Select(n => $"Temp {n:00}[℃]").ToArray()),
        ("epo", "EPO 상태 / 차단시각", ["EPO 버튼"]) ];

    private readonly object _gate = new(); private readonly string _outputDirectory;
    private readonly Dictionary<DateOnly, List<object?[]>> _rows = []; private System.Threading.Timer? _timer;
    private Func<MonitorSnapshot?>? _snapshotProvider; private OperationRecordOptions? _options; private string _sessionId = "";
    public bool IsRecording => _timer is not null; public DateTime? EndsAt { get; private set; }
    public event EventHandler<string>? FileSaved; public event EventHandler<string>? Error;

    public OperationRecordService(string outputDirectory) => _outputDirectory = outputDirectory;
    public void Start(OperationRecordOptions options, Func<MonitorSnapshot?> snapshotProvider)
    {
        if (IsRecording) return; if (options.Fields.Count == 0) throw new ArgumentException("기록 항목을 하나 이상 선택하세요.");
        Directory.CreateDirectory(_outputDirectory); _options = options; _snapshotProvider = snapshotProvider; var now = DateTime.Now;
        _sessionId = now.ToString("yyyy-MM-dd_HH-mm-ss_ffffff", CultureInfo.InvariantCulture); EndsAt = now.AddDays(Math.Clamp(options.DurationDays, 1, 30));
        _timer = new System.Threading.Timer(_ => RecordSafely(), null, TimeSpan.Zero, TimeSpan.FromMinutes(Math.Max(1, options.IntervalMinutes)));
    }
    public void Stop() { var timer = Interlocked.Exchange(ref _timer, null); timer?.Dispose(); EndsAt = null; }
    public void RecordNow() => RecordSafely();

    private void RecordSafely()
    {
        try
        {
            if (!IsRecording || _options is null) return; if (DateTime.Now >= EndsAt) { Stop(); return; }
            var snapshot = _snapshotProvider?.Invoke(); if (snapshot is null || snapshot.Connection != ConnectionState.Connected) return;
            var recordedAt = DateTime.Now; var rows = CreateRows(snapshot, recordedAt, _options.Fields); if (rows.Count == 0) return;
            string path;
            lock (_gate)
            {
                var date = DateOnly.FromDateTime(recordedAt); if (!_rows.TryGetValue(date, out var stored)) _rows[date] = stored = [];
                stored.AddRange(rows); path = Path.Combine(_outputDirectory, $"Operation_data_{_sessionId}_{date:yyyy-MM-dd}.xlsx");
                SimpleXlsxWriter.Write(path, CreateHeaders(_options.Fields), stored);
            }
            FileSaved?.Invoke(this, path);
        }
        catch (Exception ex) { Error?.Invoke(this, ex.Message); }
    }

    public static string[] CreateHeaders(IReadOnlySet<string> fields) => ["기록시각", "모듈", .. FieldSpecs.Where(s => fields.Contains(s.Key)).SelectMany(s => s.Headers)];
    public static List<object?[]> CreateRows(MonitorSnapshot snapshot, DateTime at, IReadOnlySet<string> fields)
    {
        var result = new List<object?[]>();
        foreach (var m in snapshot.Modules.Where(m => m.Connected).OrderBy(m => m.Number))
        {
            var cells = m.CellVoltages; var temps = m.CellTemperatures; var validCells = cells.Where(v => v.HasValue).Select(v => v!.Value).ToArray(); var validTemps = temps.Where(v => v.HasValue).Select(v => v!.Value).ToArray();
            var values = new Dictionary<string, object?[]> {
                ["equipment"] = [m.RowIndex, m.EquipmentId, m.Model, m.Barcode], ["voltage"] = [m.Voltage], ["current"] = [m.Current], ["soc_soh"] = [m.Soc, m.Soh],
                ["status"] = [m.Status, m.Connected ? "통신중" : "차단"], ["alarm"] = [m.Alarm == AlarmLevel.Normal ? "정상" : "이상"],
                ["cell_summary"] = [validCells.Length > 0 ? validCells.Max() : null, validCells.Length > 0 ? validCells.Min() : null], ["cell_detail"] = cells.Cast<object?>().ToArray(),
                ["temp_summary"] = [validTemps.Length > 0 ? validTemps.Max() : null, validTemps.Length > 0 ? validTemps.Min() : null], ["temp_detail"] = temps.Cast<object?>().ToArray(), ["epo"] = ["차단"] };
            var row = new List<object?> { at.ToString("yyyy-MM-dd HH:mm:ss"), $"#{m.Number:00}" }; foreach (var spec in FieldSpecs) if (fields.Contains(spec.Key)) row.AddRange(values[spec.Key]); result.Add(row.ToArray());
        }
        return result;
    }
    public ValueTask DisposeAsync() { Stop(); return ValueTask.CompletedTask; }
}
