using System.Collections.Concurrent;
using System.Net;
using System.Net.NetworkInformation;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging;

namespace SafeChild;

public sealed record LanAddress(string Name, IPAddress Address, IPAddress Mask)
{
    public override string ToString() => $"{Name} — {Address}";
    public bool Contains(IPAddress? peer)
    {
        if (peer is null) return false;
        var bytes = peer.MapToIPv4().GetAddressBytes();
        var local = Address.GetAddressBytes();
        var mask = Mask.GetAddressBytes();
        return bytes.Length == 4 && Enumerable.Range(0, 4).All(i => (bytes[i] & mask[i]) == (local[i] & mask[i]));
    }
    public static List<LanAddress> Find() => NetworkInterface.GetAllNetworkInterfaces()
        .Where(n => n.OperationalStatus == OperationalStatus.Up && n.NetworkInterfaceType is NetworkInterfaceType.Ethernet or NetworkInterfaceType.Wireless80211)
        .SelectMany(n => n.GetIPProperties().UnicastAddresses
            .Where(a => a.Address.AddressFamily == AddressFamily.InterNetwork && IsPrivate(a.Address))
            .Select(a => new LanAddress(n.Name, a.Address, a.IPv4Mask))).ToList();
    private static bool IsPrivate(IPAddress address)
    {
        var b = address.GetAddressBytes();
        return b[0] == 10 || b[0] == 192 && b[1] == 168 || b[0] == 172 && b[1] is >= 16 and <= 31;
    }
}

public sealed record MobileStatus(bool AllowAll, DateTimeOffset? Until, int RemainingSeconds, string? Error);

public sealed class MobileControlServer : IAsyncDisposable
{
    public const int Port = 47831;
    private readonly Func<string, Task<bool>> _verify;
    private readonly Func<int?, Task<MobileStatus>> _control;
    private readonly ConcurrentDictionary<string, long> _sessions = new();
    private readonly Queue<long> _loginAttempts = new();
    private readonly SemaphoreSlim _loginGate = new(1, 1);
    private WebApplication? _app;
    private X509Certificate2? _certificate;
    public string? Url { get; private set; }
    public string? CertificateFingerprint => _certificate?.GetCertHashString(HashAlgorithmName.SHA256);

    public MobileControlServer(Func<string, Task<bool>> verify, Func<int?, Task<MobileStatus>> control)
    { _verify = verify; _control = control; }

    public async Task StartAsync(LanAddress lan, int port = Port)
    {
        if (_app is not null) throw new InvalidOperationException("이미 연결 서버가 실행 중입니다.");
        using var rsa = RSA.Create(2048);
        var request = new CertificateRequest("CN=SafeChild Local Control", rsa, HashAlgorithmName.SHA256, RSASignaturePadding.Pkcs1);
        var san = new SubjectAlternativeNameBuilder(); san.AddIpAddress(lan.Address);
        request.CertificateExtensions.Add(san.Build());
        request.CertificateExtensions.Add(new X509BasicConstraintsExtension(false, false, 0, true));
        request.CertificateExtensions.Add(new X509KeyUsageExtension(X509KeyUsageFlags.DigitalSignature | X509KeyUsageFlags.KeyEncipherment, true));
        request.CertificateExtensions.Add(new X509EnhancedKeyUsageExtension(new OidCollection { new("1.3.6.1.5.5.7.3.1") }, false));
        using var generated = request.CreateSelfSigned(DateTimeOffset.UtcNow.AddMinutes(-5), DateTimeOffset.UtcNow.AddDays(30));
        // Windows TLS needs a key container; omitting PersistKeySet removes it on disposal.
        _certificate = new X509Certificate2(generated.Export(X509ContentType.Pfx), (string?)null, X509KeyStorageFlags.UserKeySet);
        var token = Convert.ToHexString(RandomNumberGenerator.GetBytes(24));
        var prefix = "/" + token;
        var origin = $"https://{lan.Address}:{port}";
        Url = origin + prefix;
        var builder = WebApplication.CreateSlimBuilder(new WebApplicationOptions { Args = [], ContentRootPath = AppContext.BaseDirectory });
        builder.Logging.ClearProviders();
        builder.WebHost.ConfigureKestrel(options =>
        {
            options.AddServerHeader = false;
            options.Limits.MaxRequestBodySize = 4096;
            options.Limits.MaxConcurrentConnections = 16;
            options.Limits.RequestHeadersTimeout = TimeSpan.FromSeconds(10);
            options.Listen(lan.Address, port, listen => listen.UseHttps(_certificate));
        });
        var app = builder.Build();
        app.Run(async context =>
        {
            context.Response.Headers.CacheControl = "no-store";
            context.Response.Headers["Referrer-Policy"] = "no-referrer";
            context.Response.Headers["X-Content-Type-Options"] = "nosniff";
            context.Response.Headers["X-Frame-Options"] = "DENY";
            if (!lan.Contains(context.Connection.RemoteIpAddress) || context.Request.Host.Value != $"{lan.Address}:{port}")
            { context.Response.StatusCode = 403; return; }
            var path = context.Request.Path.Value;
            if (!context.Request.Path.StartsWithSegments(prefix)) { context.Response.StatusCode = 404; return; }
            try
            {
                if (context.Request.Method == "GET" && (path == prefix || path == prefix + "/"))
                {
                    var nonce = Convert.ToBase64String(RandomNumberGenerator.GetBytes(18));
                    context.Response.Headers.ContentSecurityPolicy = $"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'";
                    context.Response.ContentType = "text/html; charset=utf-8";
                    using var resource = typeof(MobileControlServer).Assembly.GetManifestResourceStream("SafeChild.MobileControl.html")!;
                    using var reader = new StreamReader(resource);
                    await context.Response.WriteAsync((await reader.ReadToEndAsync()).Replace("__NONCE__", nonce));
                    return;
                }
                if (context.Request.Method == "POST" &&
                    (context.Request.Headers.Origin != origin || context.Request.Headers["X-SafeChild"] != "1" || !context.Request.HasJsonContentType()))
                { context.Response.StatusCode = 403; return; }
                if (path == prefix + "/api/login" && context.Request.Method == "POST")
                {
                    if (!await _loginGate.WaitAsync(0)) { context.Response.StatusCode = 429; return; }
                    try
                    {
                        var now = Environment.TickCount64;
                        while (_loginAttempts.TryPeek(out var attempt) && attempt < now - 60000) _loginAttempts.Dequeue();
                        if (_loginAttempts.Count >= 5) { context.Response.StatusCode = 429; return; }
                        _loginAttempts.Enqueue(now);
                        var input = await context.Request.ReadFromJsonAsync<LoginInput>();
                        if (input?.Password is not { Length: > 0 and <= 1024 } password || !await _verify(password))
                        { context.Response.StatusCode = 401; return; }
                        foreach (var entry in _sessions.Where(x => x.Value <= now)) _sessions.TryRemove(entry.Key, out _);
                        if (_sessions.Count >= 16) { context.Response.StatusCode = 429; return; }
                        var session = Convert.ToHexString(RandomNumberGenerator.GetBytes(32));
                        _sessions[session] = now + 15 * 60000;
                        context.Response.Cookies.Append("SafeChildSession", session, new CookieOptions
                        { HttpOnly = true, Secure = true, SameSite = SameSiteMode.Strict, Path = prefix, MaxAge = TimeSpan.FromMinutes(15), IsEssential = true });
                        await context.Response.WriteAsJsonAsync(await _control(null));
                    }
                    finally { _loginGate.Release(); }
                    return;
                }
                if (!context.Request.Cookies.TryGetValue("SafeChildSession", out var id) ||
                    !_sessions.TryGetValue(id, out var expires) || expires <= Environment.TickCount64)
                { context.Response.StatusCode = 401; return; }
                if (path == prefix + "/api/status" && context.Request.Method == "GET")
                    await context.Response.WriteAsJsonAsync(await _control(null));
                else if (path == prefix + "/api/allow" && context.Request.Method == "POST")
                {
                    var input = await context.Request.ReadFromJsonAsync<AllowInput>();
                    if (input is null || input.Minutes is < 0 or > 1440) { context.Response.StatusCode = 400; return; }
                    var status = await _control(input.Minutes);
                    if (status.Error is not null) context.Response.StatusCode = 503;
                    await context.Response.WriteAsJsonAsync(status);
                }
                else if (path == prefix + "/api/logout" && context.Request.Method == "POST")
                {
                    _sessions.TryRemove(id, out _);
                    context.Response.Cookies.Delete("SafeChildSession", new CookieOptions { Path = prefix, Secure = true, SameSite = SameSiteMode.Strict });
                    context.Response.StatusCode = 204;
                }
                else context.Response.StatusCode = 404;
            }
            catch (Exception ex) when (ex is System.Text.Json.JsonException or BadHttpRequestException)
            { context.Response.StatusCode = 400; }
            catch (Exception)
            {
                context.Response.StatusCode = 503;
                await context.Response.WriteAsJsonAsync(new { error = "PC에서 요청을 처리하지 못했습니다. PC 상태를 확인하세요." });
            }
        });
        try { await app.StartAsync().ConfigureAwait(false); _app = app; }
        catch { await app.DisposeAsync(); _certificate.Dispose(); _certificate = null; Url = null; throw; }
    }

    public async ValueTask DisposeAsync()
    {
        if (_app is { } app)
        {
            _app = null;
            using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(2));
            try { await app.StopAsync(timeout.Token).ConfigureAwait(false); }
            finally { await app.DisposeAsync().ConfigureAwait(false); }
        }
        _sessions.Clear(); _certificate?.Dispose(); _certificate = null; Url = null;
    }

    private sealed record LoginInput(string Password);
    private sealed record AllowInput(int Minutes);
}
