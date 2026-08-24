using TBC1000B.WinForms.Models;
using TBC1000B.WinForms.Snmp;

namespace TBC1000B.WinForms.Services;

public sealed class SnmpMonitorService : IMonitorService
{
    private static readonly string[] BaseOids = [
        "1.3.6.1.4.1.2011.6.164.1.18.1", "1.3.6.1.4.1.2011.6.164.1.18.2",
        "1.3.6.1.4.1.2011.6.164.1.17.1", "1.3.6.1.4.1.2011.6.164.1.17.2",
        "1.3.6.1.4.1.2011.6.164.1.1.2.99" ];
    private const string SysUpTime = "1.3.6.1.2.1.1.3.0";
    private const string ChargeLimitOid = "1.3.6.1.4.1.2011.6.164.1.17.2.1.13.96";
    private const string SocEnableOid = "1.3.6.1.4.1.2011.6.164.1.17.2.1.29.96";
    private const string SocValueOid = "1.3.6.1.4.1.2011.6.164.1.17.2.1.30.96";
    private const string TrapRetransmitOid = "1.3.6.1.4.1.2011.6.164.1.1.2.4.0";
    private readonly SnmpClient _client = new();
    private readonly SnmpTrapReceiver _trapReceiver = new();
    private readonly MonitorSnapshot _snapshot = new();
    private CancellationTokenSource? _session;
    private Task? _pollTask, _trapTask;
    private ConnectionOptions? _options;
    public event EventHandler<MonitorSnapshot>? SnapshotChanged;
    public event EventHandler<TrapEntry>? TrapReceived;
    public event EventHandler<IReadOnlyDictionary<string, string>>? RawTrapReceived;
    public event EventHandler<string>? TrapListenerFailed;

    public SnmpMonitorService() => _trapReceiver.MessageReceived += OnTrapMessage;

    public async Task ConnectAsync(ConnectionOptions options, CancellationToken cancellationToken)
    {
        await DisconnectAsync(); _options = options; _snapshot.Connection = ConnectionState.Connecting; _snapshot.LastError = null; RaiseSnapshot();
        using var linked = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken); linked.CancelAfter(TimeSpan.FromSeconds(6));
        try { await _client.GetAsync(options.Address, options.Port, options.GetCommunity, [SysUpTime], linked.Token); }
        catch (Exception ex) { _snapshot.Connection = ConnectionState.Disconnected; _snapshot.LastError = ex.Message; RaiseSnapshot(); throw; }
        _session = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken); _snapshot.Connection = ConnectionState.Connected; _snapshot.UpdatedAt = DateTime.Now; RaiseSnapshot();
        _pollTask = PollAsync(_session.Token); _trapTask = options.EnableTrapListener ? RunTrapAsync(_session.Token) : Task.CompletedTask;
    }

    public async Task DisconnectAsync()
    {
        var session = _session; _session = null; if (session is null) return; session.Cancel();
        var tasks = new[] { _pollTask, _trapTask }.Where(t => t is not null).Cast<Task>().ToArray(); try { await Task.WhenAll(tasks); } catch (OperationCanceledException) { }
        session.Dispose(); _pollTask = null; _trapTask = null; _snapshot.Connection = ConnectionState.Disconnected; RaiseSnapshot();
    }

    public async Task SetEpoAsync(int? moduleNumber, bool cutoff, CancellationToken cancellationToken)
    {
        var options = _options ?? throw new InvalidOperationException("SNMP가 연결되지 않았습니다.");
        await SetVerifiedAsync("1.3.6.1.4.1.2011.6.164.1.2.2.1.1.11.1", 1);
        if (moduleNumber is not { } number || number is < 1 or > 10) return;
        var rowIndex = _snapshot.Modules[number - 1].RowIndex; if (rowIndex.Length == 0) throw new InvalidOperationException($"모듈 #{number:00}의 SNMP 행 인덱스를 찾을 수 없습니다.");
        await SetVerifiedAsync($"1.3.6.1.4.1.2011.6.164.1.18.3.1.2.{rowIndex}", cutoff ? 2 : 1);
        async Task SetVerifiedAsync(string oid, int expected)
        {
            cancellationToken.ThrowIfCancellationRequested(); var response = await _client.SetAsync(options.Address, options.Port, options.SetCommunity, new SnmpVariable(oid, SnmpDataType.Integer, expected));
            if (response.Count == 0 || response[0].Oid != oid || response[0].DisplayValue != expected.ToString()) throw new InvalidDataException($"SNMP SET 응답 불일치: {oid}");
        }
    }

    public async Task<int> GetChargeLimitAsync(CancellationToken cancellationToken)
    {
        var value = await GetSingleAsync(ChargeLimitOid, cancellationToken); return ParseInt(value, ChargeLimitOid);
    }
    public async Task SetChargeLimitAsync(int value, CancellationToken cancellationToken)
    {
        if (value is < 5 or > 105) throw new ArgumentOutOfRangeException(nameof(value), "충전전류 제한값은 5~105 범위여야 합니다.");
        await SetVerifiedAsync(ChargeLimitOid, SnmpDataType.Gauge32, value, cancellationToken); var read = await GetChargeLimitAsync(cancellationToken); if (read != value) throw new InvalidDataException($"충전전류 제한 검증 불일치: 설정 {value}, 장비 {read}");
    }
    public async Task<(int Enabled, int Value)> GetSocChargeLimitAsync(CancellationToken cancellationToken)
    {
        var options = RequireOptions(); var values = await _client.GetAsync(options.Address, options.Port, options.GetCommunity, [SocEnableOid, SocValueOid], cancellationToken); if (values.Count < 2) throw new InvalidDataException("SOC 제한 GET 응답이 부족합니다."); return (ParseInt(values[0], SocEnableOid), ParseInt(values[1], SocValueOid));
    }
    public async Task SetSocChargeLimitAsync(int enabled, int? value, CancellationToken cancellationToken)
    {
        if (enabled is not (1 or 2)) throw new ArgumentOutOfRangeException(nameof(enabled), "SOC 제한 상태는 1 또는 2여야 합니다."); if (enabled == 2 && value is not (>= 1 and <= 100)) throw new ArgumentOutOfRangeException(nameof(value), "SOC 제한값은 1~100 범위여야 합니다.");
        await SetVerifiedAsync(SocEnableOid, SnmpDataType.Integer, enabled, cancellationToken); if (enabled == 2) { await Task.Delay(100, cancellationToken); await SetVerifiedAsync(SocValueOid, SnmpDataType.Gauge32, value!.Value, cancellationToken); }
        var read = await GetSocChargeLimitAsync(cancellationToken); if (read.Enabled != enabled || (enabled == 2 && read.Value != value)) throw new InvalidDataException($"SOC 제한 검증 불일치: 설정 {enabled}/{value}, 장비 {read.Enabled}/{read.Value}");
    }
    public Task RequestTrapRetransmissionAsync(CancellationToken cancellationToken) => SetVerifiedAsync(TrapRetransmitOid, SnmpDataType.Integer, 1, cancellationToken);

    private ConnectionOptions RequireOptions() => _options ?? throw new InvalidOperationException("SNMP가 연결되지 않았습니다.");
    private async Task<SnmpVariable> GetSingleAsync(string oid, CancellationToken token) { var o = RequireOptions(); var values = await _client.GetAsync(o.Address, o.Port, o.GetCommunity, [oid], token); return values.SingleOrDefault() ?? throw new InvalidDataException($"SNMP GET 응답 없음: {oid}"); }
    private async Task SetVerifiedAsync(string oid, SnmpDataType type, int expected, CancellationToken token) { token.ThrowIfCancellationRequested(); var o = RequireOptions(); var values = await _client.SetAsync(o.Address, o.Port, o.SetCommunity, new SnmpVariable(oid, type, expected)); if (values.Count == 0 || values[0].Oid != oid || ParseInt(values[0], oid) != expected) throw new InvalidDataException($"SNMP SET 응답 불일치: {oid}"); }
    private static int ParseInt(SnmpVariable value, string oid) => int.TryParse(value.DisplayValue, out var parsed) ? parsed : throw new InvalidDataException($"SNMP 정수값 오류: {oid}={value.DisplayValue}");

    private async Task PollAsync(CancellationToken token)
    {
        var options = _options!;
        while (!token.IsCancellationRequested)
        {
            try
            {
                var cycle = new Dictionary<string, string>(StringComparer.Ordinal);
                // 실제 TBC1000B에서 30개 응답은 UDP 단편화/유실로 timeout이 발생했다.
                // 10개 단위는 동일 장비의 577개 OID를 누락 없이 안정적으로 수집했다.
                foreach (var oid in BaseOids) { var values = await _client.WalkBulkAsync(options.Address, options.Port, options.GetCommunity, oid, 10, token); foreach (var value in values) cycle[value.Oid] = value.DisplayValue; await Task.Delay(10, token); }
                lock (_snapshot) { _snapshot.RawValues.Clear(); foreach (var item in cycle) _snapshot.RawValues[item.Key] = item.Value; _snapshot.UpdatedAt = DateTime.Now; _snapshot.LastError = null; _snapshot.ConsecutiveFailures = 0; }
                SnmpDataMapper.Apply(_snapshot, cycle);
                RaiseSnapshot();
            }
            catch (OperationCanceledException) when (token.IsCancellationRequested) { break; }
            catch (Exception ex) { _snapshot.LastError = ex.Message; _snapshot.ConsecutiveFailures++; _snapshot.TotalFailures++; if (_snapshot.ConsecutiveFailures >= 30) { _snapshot.Connection = ConnectionState.Disconnected; _session?.Cancel(); } RaiseSnapshot(); if (_snapshot.ConsecutiveFailures >= 30) break; }
            await Task.Delay(TimeSpan.FromSeconds(2), token);
        }
    }

    private async Task RunTrapAsync(CancellationToken token)
    {
        try { await _trapReceiver.RunAsync(_options!.TrapPort, _options.TrapCommunity, token); }
        catch (Exception ex) when (ex is not OperationCanceledException) { _snapshot.LastError = $"Trap UDP {_options!.TrapPort}: {ex.Message}"; TrapListenerFailed?.Invoke(this, ex.Message); RaiseSnapshot(); }
    }

    private void OnTrapMessage(object? sender, (SnmpMessage Message, System.Net.IPEndPoint Source) data)
    {
        var raw = data.Message.Variables.ToDictionary(v => v.Oid, v => v.DisplayValue, StringComparer.Ordinal); raw["_source_ip"] = data.Source.Address.ToString(); var entry = TrapDataParser.Parse(raw);
        lock (_snapshot) { _snapshot.Traps.Insert(0, entry); if (_snapshot.Traps.Count > 1000) _snapshot.Traps.RemoveAt(_snapshot.Traps.Count - 1); _snapshot.UpdatedAt = DateTime.Now; }
        RawTrapReceived?.Invoke(this, raw); TrapReceived?.Invoke(this, entry); RaiseSnapshot();
    }
    private void RaiseSnapshot() => SnapshotChanged?.Invoke(this, _snapshot);
    public async ValueTask DisposeAsync() { await DisconnectAsync(); await _trapReceiver.DisposeAsync(); }
}
