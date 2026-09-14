using System.Net;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging;

namespace SafeChild;

public sealed class BrowserMessageServer : IAsyncDisposable
{
    public const int Port = 47832;
    public const string ExtensionId = "lkhmbejdgajboeegpgialmlikdalcldk";
    private readonly Func<Task<string[]>> _domains;
    private readonly Func<string, Task> _visit;
    private WebApplication? _app;
    private int _clients;
    private readonly CancellationTokenSource _stopping = new();
    public int ClientCount => Volatile.Read(ref _clients);

    public BrowserMessageServer(Func<Task<string[]>> domains, Func<string, Task> visit) { _domains = domains; _visit = visit; }

    public async Task StartAsync(int port = Port)
    {
        var builder = WebApplication.CreateSlimBuilder(new WebApplicationOptions { Args = [], ContentRootPath = AppContext.BaseDirectory });
        builder.Logging.ClearProviders();
        builder.WebHost.ConfigureKestrel(options =>
        {
            options.AddServerHeader = false;
            options.Limits.MaxConcurrentConnections = 8;
            options.Limits.MaxRequestBodySize = 4096;
            options.Listen(IPAddress.Loopback, port);
        });
        var app = builder.Build();
        app.UseWebSockets();
        app.Run(async context =>
        {
            if (context.Request.Path != "/browser" || context.Request.Host.Value != $"127.0.0.1:{port}" ||
                context.Connection.RemoteIpAddress is not { } ip || !IPAddress.IsLoopback(ip) ||
                context.Request.Headers.Origin != $"chrome-extension://{ExtensionId}")
            { context.Response.StatusCode = 403; return; }
            if (!context.WebSockets.IsWebSocketRequest) { context.Response.StatusCode = 400; return; }
            using var socket = await context.WebSockets.AcceptWebSocketAsync();
            using var cancellation = CancellationTokenSource.CreateLinkedTokenSource(context.RequestAborted, _stopping.Token);
            Interlocked.Increment(ref _clients);
            try
            {
                var send = SendPolicies(socket, cancellation.Token);
                var receive = ReceiveVisits(socket, cancellation.Token);
                await Task.WhenAny(send, receive);
                cancellation.Cancel();
                try { await Task.WhenAll(send, receive); } catch (Exception) { /* Disconnect ends both loops. */ }
            }
            finally { Interlocked.Decrement(ref _clients); }
        });
        try { await app.StartAsync().ConfigureAwait(false); _app = app; }
        catch { await app.DisposeAsync(); throw; }
    }

    private async Task SendPolicies(WebSocket socket, CancellationToken token)
    {
        while (!token.IsCancellationRequested)
        {
            var domains = await _domains().WaitAsync(token);
            var bytes = JsonSerializer.SerializeToUtf8Bytes(new { type = "domains", domains });
            await socket.SendAsync(bytes.AsMemory(), WebSocketMessageType.Text, true, token);
            await Task.Delay(1000, token);
        }
    }

    private async Task ReceiveVisits(WebSocket socket, CancellationToken token)
    {
        var buffer = new byte[4096];
        long lastVisit = -1000;
        while (!token.IsCancellationRequested)
        {
            var length = 0;
            ValueWebSocketReceiveResult part;
            do
            {
                part = await socket.ReceiveAsync(buffer.AsMemory(length), token);
                if (part.MessageType == WebSocketMessageType.Close) return;
                if (part.MessageType != WebSocketMessageType.Text) return;
                length += part.Count;
                if (length >= buffer.Length) return;
            } while (!part.EndOfMessage);
            var now = Environment.TickCount64;
            if (now - lastVisit < 500) continue;
            lastVisit = now;
            try
            {
                using var json = JsonDocument.Parse(buffer.AsMemory(0, length));
                if (json.RootElement.TryGetProperty("url", out var url) && url.ValueKind == JsonValueKind.String && url.GetString() is { } value)
                    await _visit(value).WaitAsync(token);
            }
            catch (JsonException) { /* Ignore malformed extension messages. */ }
        }
    }

    public async ValueTask DisposeAsync()
    {
        if (_app is not { } app) return;
        _app = null;
        _stopping.Cancel();
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(2));
        try { await app.StopAsync(timeout.Token).ConfigureAwait(false); }
        finally { await app.DisposeAsync().ConfigureAwait(false); }
    }
}
