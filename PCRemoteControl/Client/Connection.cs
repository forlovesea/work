using System.Buffers.Binary;
using System.Net.Security;
using System.Net.Sockets;
using System.Text.Json;

namespace PCRemoteControl;
sealed class Connection : IDisposable
{
    readonly TcpClient tcp = new() { NoDelay = true };
    readonly SemaphoreSlim gate = new(1);
    SslStream stream = null!;
    public async Task Open(string host, int port, object hello, CancellationToken token)
    {
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(token);
        timeout.CancelAfter(TimeSpan.FromSeconds(15));
        await tcp.ConnectAsync(host, port, timeout.Token);
        stream = new SslStream(tcp.GetStream(), false);
        await stream.AuthenticateAsClientAsync(new SslClientAuthenticationOptions { TargetHost = host }, timeout.Token);
        await Send(hello, timeout.Token);
        var answer = await Read(timeout.Token);
        if (answer.GetProperty("type").GetString() != "ok")
            throw new IOException(answer.GetProperty("message").GetString());
    }
    public async Task Send(object message, CancellationToken token)
    {
        byte[] raw = JsonSerializer.SerializeToUtf8Bytes(message);
        if (raw.Length > 8 * 1024 * 1024) throw new IOException("Frame too large");
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(token);
        timeout.CancelAfter(TimeSpan.FromSeconds(10));
        await gate.WaitAsync(timeout.Token);
        try
        {
            byte[] header = new byte[4];
            BinaryPrimitives.WriteInt32BigEndian(header, raw.Length);
            await stream.WriteAsync(header, timeout.Token);
            await stream.WriteAsync(raw, timeout.Token);
        }
        finally { gate.Release(); }
    }
    public async Task<JsonElement> Read(CancellationToken token)
    {
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(token);
        timeout.CancelAfter(TimeSpan.FromSeconds(35));
        byte[] header = new byte[4];
        await stream.ReadExactlyAsync(header, timeout.Token);
        int length = BinaryPrimitives.ReadInt32BigEndian(header);
        if (length <= 0 || length > 8 * 1024 * 1024) throw new IOException("Invalid message length");
        byte[] raw = new byte[length];
        await stream.ReadExactlyAsync(raw, timeout.Token);
        using var doc = JsonDocument.Parse(raw);
        return doc.RootElement.Clone();
    }
    public void Dispose() { tcp.Dispose(); stream?.Dispose(); }
}
