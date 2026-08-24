using System.Net;
using System.Net.Sockets;

namespace TBC1000B.WinForms.Snmp;

public sealed class SnmpTrapReceiver : IAsyncDisposable
{
    private UdpClient? _udp;
    public event EventHandler<(SnmpMessage Message, IPEndPoint Source)>? MessageReceived;

    public async Task RunAsync(int port, string community, CancellationToken token)
    {
        _udp = new UdpClient(new IPEndPoint(IPAddress.Any, port));
        try
        {
            while (!token.IsCancellationRequested)
            {
                var result = await _udp.ReceiveAsync(token); SnmpMessage message;
                try { message = SnmpCodec.Decode(result.Buffer); } catch (InvalidDataException) { continue; }
                if (message.PduType != SnmpCodec.TrapV2 || !string.Equals(message.Community, community, StringComparison.Ordinal)) continue;
                MessageReceived?.Invoke(this, (message, result.RemoteEndPoint));
            }
        }
        catch (OperationCanceledException) when (token.IsCancellationRequested) { }
        finally { _udp.Dispose(); _udp = null; }
    }
    public ValueTask DisposeAsync() { _udp?.Dispose(); _udp = null; return ValueTask.CompletedTask; }
}
