using TBC1000B.WinForms.Models;

namespace TBC1000B.WinForms.Services;

public sealed record ConnectionOptions(string Address, int Port, string GetCommunity,
    string SetCommunity, string TrapCommunity, int TrapPort, bool EnableTrapListener = true);

public interface IMonitorService : IAsyncDisposable
{
    event EventHandler<MonitorSnapshot>? SnapshotChanged;
    event EventHandler<TrapEntry>? TrapReceived;
    event EventHandler<IReadOnlyDictionary<string, string>>? RawTrapReceived;
    event EventHandler<string>? TrapListenerFailed;
    Task ConnectAsync(ConnectionOptions options, CancellationToken cancellationToken);
    Task DisconnectAsync();
    Task SetEpoAsync(int? moduleNumber, bool cutoff, CancellationToken cancellationToken);
    Task<int> GetChargeLimitAsync(CancellationToken cancellationToken);
    Task SetChargeLimitAsync(int value, CancellationToken cancellationToken);
    Task<(int Enabled, int Value)> GetSocChargeLimitAsync(CancellationToken cancellationToken);
    Task SetSocChargeLimitAsync(int enabled, int? value, CancellationToken cancellationToken);
    Task RequestTrapRetransmissionAsync(CancellationToken cancellationToken);
}

// UI 포팅 단계용 서비스. 실제 SNMP 구현은 이 인터페이스 뒤에 연결한다.
public sealed class PreviewMonitorService : IMonitorService
{
    private readonly MonitorSnapshot _snapshot = new();
    public event EventHandler<MonitorSnapshot>? SnapshotChanged;
    public event EventHandler<TrapEntry>? TrapReceived { add { } remove { } }
    public event EventHandler<IReadOnlyDictionary<string, string>>? RawTrapReceived { add { } remove { } }
    public event EventHandler<string>? TrapListenerFailed { add { } remove { } }

    public async Task ConnectAsync(ConnectionOptions options, CancellationToken cancellationToken)
    {
        _snapshot.Connection = ConnectionState.Connecting;
        SnapshotChanged?.Invoke(this, _snapshot);
        await Task.Delay(350, cancellationToken);
        _snapshot.Connection = ConnectionState.Connected;
        _snapshot.UpdatedAt = DateTime.Now;
        SnapshotChanged?.Invoke(this, _snapshot);
    }

    public Task DisconnectAsync()
    {
        _snapshot.Connection = ConnectionState.Disconnected;
        SnapshotChanged?.Invoke(this, _snapshot);
        return Task.CompletedTask;
    }

    public Task SetEpoAsync(int? moduleNumber, bool cutoff, CancellationToken cancellationToken) => Task.CompletedTask;
    public Task<int> GetChargeLimitAsync(CancellationToken cancellationToken) => Task.FromResult(50);
    public Task SetChargeLimitAsync(int value, CancellationToken cancellationToken) => Task.CompletedTask;
    public Task<(int Enabled, int Value)> GetSocChargeLimitAsync(CancellationToken cancellationToken) => Task.FromResult((2, 95));
    public Task SetSocChargeLimitAsync(int enabled, int? value, CancellationToken cancellationToken) => Task.CompletedTask;
    public Task RequestTrapRetransmissionAsync(CancellationToken cancellationToken) => Task.CompletedTask;
    public ValueTask DisposeAsync() => ValueTask.CompletedTask;
}
