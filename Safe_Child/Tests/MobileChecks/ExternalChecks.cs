using System.Net;
using System.Net.Http.Json;
using System.Net.Security;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using System.Text.Json;
using SafeChild;

internal static class ExternalChecks
{
    public static async Task Run(Action<bool, string> check)
    {
        void Invalid(Action action, string name)
        {
            try { action(); throw new Exception("Expected invalid input: " + name); }
            catch (ArgumentException) { check(true, name); }
        }
        var lan = new LanAddress("test", IPAddress.Loopback, IPAddress.Parse("255.0.0.0"));
        const string origin = "https://parent.example.test:44443";
        var local = new MobileEndpointPolicy(lan, 47831);
        var external = new MobileEndpointPolicy(lan, 47831, origin);
        check(!local.Allows(IPAddress.Parse("203.0.113.8"), "127.0.0.1:47831"), "LAN mode rejects outside peer");
        check(external.Allows(IPAddress.Parse("203.0.113.8"), "parent.example.test:44443"), "External mode accepts remote peer with registered host");
        check(!external.Allows(IPAddress.Loopback, "evil.example.test:44443"), "Unregistered Host rejected");
        check(!external.Allows(IPAddress.Loopback, "parent.example.test:47831"), "Host uses external port, not internal port");
        check(external.AllowsOrigin(origin) && !external.AllowsOrigin("https://evil.example.test:44443"), "Only registered origin accepted");
        check(!external.AllowsOrigin("null") && !external.AllowsOrigin(""), "Missing and null origins rejected");
        var standard = new MobileEndpointPolicy(lan, 47831, "https://PARENT.example.test:443/");
        check(standard.Origin == "https://parent.example.test" && standard.Allows(IPAddress.Loopback, "parent.example.test") &&
            standard.Allows(IPAddress.Loopback, "parent.example.test:443"), "Standard HTTPS port normalized");
        foreach (var input in new[] { "http://parent.example.test", "https://user:password@parent.example.test", "https://parent.example.test/path",
            "https://parent.example.test?token=secret", "https://parent.example.test/#x", "https://parent.example.test:0", "parent.example.test" })
            Invalid(() => MobileConnectionOptions.ParseOrigin(input), "Invalid public origin rejected: " + input);

        var args = MobileFirewall.BuildArguments("192.168.35.100", true, @"C:\Program Files\SafeChild\SafeChild.exe");
        check(args.Contains("remoteip=any") && args.Contains("localport=47831") && args.Contains("localip=192.168.35.100") &&
            args.Contains("profile=private,domain") && args.Contains(@"program=C:\Program Files\SafeChild\SafeChild.exe"), "External firewall scoped to selected address, port, program, profiles");
        check(MobileFirewall.BuildArguments("192.168.35.100", false, "SafeChild.exe").Contains("remoteip=LocalSubnet"), "LAN firewall remains local only");

        var directory = Path.Combine(Path.GetTempPath(), "SafeChild-ExternalChecks-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(directory);
        var path = Path.Combine(directory, "server.pfx");
        try
        {
            using var certificate = CreateCertificate("parent.example.test");
            File.WriteAllBytes(path, certificate.Export(X509ContentType.Pfx, "test-pfx-password"));
            var token = MobileConnectionOptions.NewAccessToken();
            var options = new MobileConnectionOptions(origin, path, "test-pfx-password", token);
            using (var loaded = options.LoadCertificate()) check(loaded.HasPrivateKey, "PFX private key loaded");
            Invalid(() => (options with { CertificatePassword = "wrong" }).LoadCertificate(), "Wrong PFX password rejected");
            Invalid(() => (options with { PublicOrigin = "https://wrong.example.test" }).LoadCertificate(), "Certificate hostname mismatch rejected");
            Invalid(() => (options with { AccessToken = "../short" }).LoadCertificate(), "Invalid link token rejected");
            using var noKey = new X509Certificate2(certificate.Export(X509ContentType.Cert));
            Invalid(() => MobileConnectionOptions.ValidateCertificate(noKey, new Uri(origin)), "Certificate without private key rejected");
            using var expired = CreateCertificate("parent.example.test", expired: true);
            Invalid(() => MobileConnectionOptions.ValidateCertificate(expired, new Uri(origin)), "Expired certificate rejected");
            using var clientOnly = CreateCertificate("parent.example.test", clientOnly: true);
            Invalid(() => MobileConnectionOptions.ValidateCertificate(clientOnly, new Uri(origin)), "Client-only certificate rejected");
            using var wildcard = CreateCertificate("*.example.test");
            MobileConnectionOptions.ValidateCertificate(wildcard, new Uri(origin));
            check(true, "Matching wildcard certificate accepted");
            Invalid(() => MobileConnectionOptions.ValidateCertificate(wildcard, new Uri("https://a.parent.example.test")), "Wildcard does not match extra label");
            var preferences = new MobileConnectionSettings { ExternalEnabled = true, PublicOrigin = origin, CertificatePath = path, AccessToken = token };
            var json = JsonSerializer.Serialize(preferences);
            check(!json.Contains("test-pfx-password") && JsonSerializer.Deserialize<MobileConnectionSettings>(json)!.AccessToken == token,
                "Preferences preserve link and never include certificate password");

            var listener = new TcpListener(IPAddress.Loopback, 0); listener.Start();
            var port = ((IPEndPoint)listener.LocalEndpoint).Port; listener.Stop();
            var settings = new AppSettings();
            await using var server = new MobileControlServer(password => Task.FromResult(password == "parent-test-password"),
                _ => Task.FromResult(new MobileStatus(false, null, 0, null)),
                command =>
                {
                    if (command is not null) MobileRules.Execute(settings, command, value => value, () => { });
                    return Task.FromResult(MobileRules.Read(settings));
                });
            await server.StartAsync(lan, port, options);
            var url = server.Url!;
            check(url == origin + "/" + token && server.External, "External URL includes public port and saved token");

            // Simulate NAT: connect to a loopback port while retaining public Host, Origin, and TLS SNI.
            var testingInvalidHost = false;
            using var handler = new SocketsHttpHandler
            {
                UseProxy = false,
                ConnectCallback = async (_, cancellation) =>
                {
                    var socket = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
                    try { await socket.ConnectAsync(IPAddress.Loopback, port, cancellation); return new NetworkStream(socket, ownsSocket: true); }
                    catch { socket.Dispose(); throw; }
                },
                SslOptions = new SslClientAuthenticationOptions
                {
                    RemoteCertificateValidationCallback = (_, presented, _, errors) =>
                        presented?.GetCertHashString() == certificate.GetCertHashString() &&
                        (testingInvalidHost || (errors & SslPolicyErrors.RemoteCertificateNameMismatch) == 0)
                }
            };
            using var client = new HttpClient(handler) { BaseAddress = new Uri(url + "/"), Timeout = TimeSpan.FromSeconds(15) };
            client.DefaultRequestHeaders.Add("Origin", origin);
            client.DefaultRequestHeaders.Add("X-SafeChild", "1");
            var page = await client.GetStringAsync("");
            check(page.Contains("관리자 비밀번호") && !page.Contains("__AUTH_LABEL__") && !page.Contains("마스터 비밀번호"), "External login page uses administrator authentication label");
            check((await client.GetAsync("api/rules")).StatusCode == HttpStatusCode.Unauthorized, "External rules require login");
            client.DefaultRequestHeaders.Host = "evil.example.test:44443";
            // HttpClient also uses Host for TLS SNI. Pin the test certificate while testing HTTP Host rejection.
            testingInvalidHost = true;
            client.DefaultRequestHeaders.Add("X-Forwarded-Host", "parent.example.test:44443");
            check((await client.GetAsync("")).StatusCode == HttpStatusCode.Forbidden, "Spoofed Host and forwarded headers rejected");
            testingInvalidHost = false;
            client.DefaultRequestHeaders.Host = null; client.DefaultRequestHeaders.Remove("X-Forwarded-Host");
            check((await client.GetAsync(origin + "/" + MobileConnectionOptions.NewAccessToken())).StatusCode == HttpStatusCode.NotFound, "Unknown external link rejected");
            check((await client.PostAsJsonAsync("api/login", new { password = "parent-test-password" })).IsSuccessStatusCode, "External login through mapped port succeeds");
            var schedule = MobileRules.ScheduleView(new DomainSchedule());
            var command = new MobileRuleCommand("save", null, null, "external.example.test", true, schedule);
            check((await client.PostAsJsonAsync("api/rules", command)).IsSuccessStatusCode && settings.Domains.Count == 1, "External authenticated rule save succeeds");
            client.DefaultRequestHeaders.Remove("Origin"); client.DefaultRequestHeaders.Add("Origin", "https://untrusted.example.test");
            check((await client.PostAsJsonAsync("api/rules", command)).StatusCode == HttpStatusCode.Forbidden, "External cross-origin write rejected");
            client.DefaultRequestHeaders.Remove("Origin"); client.DefaultRequestHeaders.Add("Origin", origin);
            server.RevokeSessions();
            check((await client.GetAsync("api/rules")).StatusCode == HttpStatusCode.Unauthorized, "Credential change revokes external sessions");
            await server.DisposeAsync();
            await server.StartAsync(lan, port, options);
            check(server.Url == url, "Restart keeps external bookmark");
            check((await client.GetAsync("api/rules")).StatusCode == HttpStatusCode.Unauthorized, "Restart does not retain logged-in sessions");
            await server.DisposeAsync();
            await server.StartAsync(lan, port, options with { AccessToken = MobileConnectionOptions.NewAccessToken() });
            check((await client.GetAsync("")).StatusCode == HttpStatusCode.NotFound, "Link rotation invalidates old external URL");
        }
        finally { File.Delete(path); Directory.Delete(directory); }
    }

    private static X509Certificate2 CreateCertificate(string domain, bool expired = false, bool clientOnly = false)
    {
        using var rsa = RSA.Create(2048);
        var request = new CertificateRequest("CN=SafeChild Test", rsa, HashAlgorithmName.SHA256, RSASignaturePadding.Pkcs1);
        var san = new SubjectAlternativeNameBuilder(); san.AddDnsName(domain); request.CertificateExtensions.Add(san.Build());
        request.CertificateExtensions.Add(new X509BasicConstraintsExtension(false, false, 0, true));
        request.CertificateExtensions.Add(new X509EnhancedKeyUsageExtension(new OidCollection
            { new(clientOnly ? "1.3.6.1.5.5.7.3.2" : "1.3.6.1.5.5.7.3.1") }, false));
        return request.CreateSelfSigned(DateTimeOffset.UtcNow.AddDays(-2), DateTimeOffset.UtcNow.AddDays(expired ? -1 : 7));
    }
}
