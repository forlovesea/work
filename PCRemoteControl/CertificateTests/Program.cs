using System.Net;
using System.Net.Security;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using PCRemoteControl;

foreach (bool expired in new[] { true, false })
{
    using var key = RSA.Create(2048);
    var request = new CertificateRequest("CN=localhost", key, HashAlgorithmName.SHA256, RSASignaturePadding.Pkcs1);
    using var generated = request.CreateSelfSigned(DateTimeOffset.UtcNow.AddDays(-2), DateTimeOffset.UtcNow.AddDays(expired ? -1 : 1));
    using var cert = new X509Certificate2(generated.Export(X509ContentType.Pfx));
    using var listener = new TcpListener(IPAddress.Loopback, 0);
    listener.Start();
    using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(10));
    var server = Task.Run(async () =>
    {
        using var peer = await listener.AcceptTcpClientAsync(timeout.Token);
        using var tls = new SslStream(peer.GetStream());
        try { await tls.AuthenticateAsServerAsync(new SslServerAuthenticationOptions { ServerCertificate = cert }, timeout.Token); }
        catch (System.Security.Authentication.AuthenticationException) { }
        catch (IOException) { }
    });
    using var connection = new Connection();
    bool askedForCode = false;
    try
    {
        await connection.Open("localhost", ((IPEndPoint)listener.LocalEndpoint).Port, new { type = "hello" }, _ => { askedForCode = true; return "123456"; }, timeout.Token);
        throw new Exception("Invalid certificate was accepted.");
    }
    catch (RelayCertificateException ex)
    {
        if (askedForCode || !ex.Message.Contains("UTC") || !ex.Message.Contains("자동 재연결을 중지"))
            throw new Exception("Missing diagnostics or authentication proceeded.");
        if (expired && !ex.Message.Contains("유효기간 오류")) throw new Exception("Expired certificate was not identified.");
        if (!expired && !ex.Message.Contains("검증 실패")) throw new Exception("Untrusted certificate was not identified.");
    }
    await server;
    Console.WriteLine(expired ? "PASS: expired certificate rejected with time guidance" : "PASS: untrusted certificate rejected without bypass");
}
