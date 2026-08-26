using System.Net;
using System.Net.Sockets;
using System.Text.Json;

namespace TBC1000B.WinForms.Services;

public sealed record SlaveStatus(string Profile, string TargetIp, int Port, string SystemName, DateTime LastSeen)
{ public bool IsAlive => DateTime.UtcNow - LastSeen <= TimeSpan.FromSeconds(12); }

public sealed class SlaveCoordinator : IAsyncDisposable
{
    public const int RegistrationPort = 50000, MinLocalPort = 51000, MaxLocalPort = 52000;
    private readonly Dictionary<string, SlaveStatus> _registry = new(StringComparer.OrdinalIgnoreCase); private readonly object _gate = new();
    private UdpClient? _registrationSocket, _localTrapSocket; private CancellationTokenSource? _cts; private Task? _receiveTask; private System.Threading.Timer? _heartbeat;
    private string _profile = "", _targetIp = "", _system = ""; private int _localPort;
    public event EventHandler<IReadOnlyDictionary<string, string>>? ForwardedTrapReceived;
    public IReadOnlyList<SlaveStatus> GetStatuses() { lock (_gate) return _registry.Values.OrderBy(v => v.Profile).ToArray(); }

    public void StartMaster(CancellationToken token)
    {
        Stop(); _cts = CancellationTokenSource.CreateLinkedTokenSource(token); _registrationSocket = new UdpClient(new IPEndPoint(IPAddress.Any, RegistrationPort)); _receiveTask = ReceiveRegistrationsAsync(_cts.Token);
    }
    public int StartSlave(string targetIp, int requestedPort, string profile, string system, CancellationToken token)
    {
        Stop(); _cts = CancellationTokenSource.CreateLinkedTokenSource(token); _targetIp = targetIp; _profile = Path.GetFileName(profile); _system = system;
        _localPort = requestedPort is >= MinLocalPort and <= MaxLocalPort && IsPortAvailable(requestedPort) ? requestedPort : FindAvailablePort();
        _localTrapSocket = new UdpClient(new IPEndPoint(IPAddress.Loopback, _localPort)); _receiveTask = ReceiveForwardedTrapsAsync(_cts.Token);
        SendRegistration("register");
        _heartbeat = new System.Threading.Timer(_ => SendRegistration("heartbeat"), null, TimeSpan.FromMilliseconds(500), TimeSpan.FromSeconds(5));
        return _localPort;
    }
    public async Task<IReadOnlyList<string>> ForwardAsync(IReadOnlyDictionary<string, string> trap)
    {
        var sourceIp = trap.TryGetValue("_source_ip", out var value) ? NormalizeIp(value) : ""; SlaveStatus[] targets; lock (_gate) targets = _registry.Values.Where(s => s.IsAlive && (sourceIp.Length == 0 || NormalizeIp(s.TargetIp) == sourceIp)).ToArray();
        var json = JsonSerializer.SerializeToUtf8Bytes(trap); var delivered = new List<string>(); using var udp = new UdpClient();
        foreach (var target in targets) { try { await udp.SendAsync(json, new IPEndPoint(IPAddress.Loopback, target.Port)); delivered.Add(target.Profile); } catch (SocketException) { } } return delivered;
    }
    private async Task ReceiveRegistrationsAsync(CancellationToken token)
    {
        while (!token.IsCancellationRequested) try
        {
            var result = await _registrationSocket!.ReceiveAsync(token); var message = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(result.Buffer); if (message is null) continue;
            var type = Text(message, "type"); var profile = Path.GetFileName(Text(message, "profile")); var ip = Text(message, "ip"); var system = Text(message, "system"); var port = Number(message, "port");
            if (profile.Length == 0 || ip.Length == 0 || port is < MinLocalPort or > MaxLocalPort || type is not ("register" or "heartbeat" or "unregister")) continue;
            lock (_gate) { if (type == "unregister") _registry.Remove(profile); else _registry[profile] = new SlaveStatus(profile, ip, port, system, DateTime.UtcNow); }
        }
        catch (OperationCanceledException) when (token.IsCancellationRequested) { break; }
        catch (SocketException) when (token.IsCancellationRequested) { break; }
        catch (SocketException) { await Task.Delay(250, token); }
        catch (JsonException) { }
    }
    private async Task ReceiveForwardedTrapsAsync(CancellationToken token)
    {
        while (!token.IsCancellationRequested) try
        {
            var result = await _localTrapSocket!.ReceiveAsync(token);
            var trap = JsonSerializer.Deserialize<Dictionary<string, string>>(result.Buffer);
            if (trap is not null && trap.ContainsKey("_source_ip")) ForwardedTrapReceived?.Invoke(this, trap);
        }
        catch (OperationCanceledException) when (token.IsCancellationRequested) { break; }
        catch (SocketException) when (token.IsCancellationRequested) { break; }
        catch (SocketException) { await Task.Delay(250, token); }
        catch (JsonException) { }
    }
    private void SendRegistration(string type)
    {
        try { using var udp = new UdpClient(); var payload = JsonSerializer.SerializeToUtf8Bytes(new { type, ip = _targetIp, port = _localPort, profile = _profile, system = _system }); udp.Send(payload, payload.Length, new IPEndPoint(IPAddress.Loopback, RegistrationPort)); } catch (SocketException) { }
    }
    private static string Text(IReadOnlyDictionary<string, JsonElement> data, string key) => data.TryGetValue(key, out var value) ? value.ToString() : "";
    private static int Number(IReadOnlyDictionary<string, JsonElement> data, string key) => data.TryGetValue(key, out var value) && value.TryGetInt32(out var number) ? number : 0;
    private static string NormalizeIp(string value) { if (value.StartsWith("::ffff:", StringComparison.OrdinalIgnoreCase)) value = value[7..]; var colon = value.IndexOf(':'); return colon > 0 ? value[..colon] : value; }
    private static bool IsPortAvailable(int port) { try { using var udp = new UdpClient(new IPEndPoint(IPAddress.Loopback, port)); return true; } catch (SocketException) { return false; } }
    private static int FindAvailablePort() { var ports = Enumerable.Range(MinLocalPort, MaxLocalPort - MinLocalPort + 1).OrderBy(_ => Random.Shared.Next()); foreach (var port in ports) if (IsPortAvailable(port)) return port; throw new IOException("51000~52000 범위에 사용 가능한 UDP 포트가 없습니다."); }
    public void Stop() { if (_localPort > 0) SendRegistration("unregister"); _heartbeat?.Dispose(); _heartbeat = null; _cts?.Cancel(); _registrationSocket?.Dispose(); _localTrapSocket?.Dispose(); _registrationSocket = null; _localTrapSocket = null; _cts?.Dispose(); _cts = null; _localPort = 0; }
    public ValueTask DisposeAsync() { Stop(); return ValueTask.CompletedTask; }
}
