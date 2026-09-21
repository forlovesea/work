using System.Net;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;

namespace SafeChild;

public sealed record MobileConnectionOptions(string PublicOrigin, string CertificatePath, string? CertificatePassword, string AccessToken)
{
    public static string NewAccessToken() => Convert.ToHexString(RandomNumberGenerator.GetBytes(24));

    public static Uri ParseOrigin(string input)
    {
        if (string.IsNullOrWhiteSpace(input) || input.Length > 2048 || input.Contains('\\') ||
            !Uri.TryCreate(input.Trim(), UriKind.Absolute, out var uri) || uri.Scheme != "https" ||
            uri.Port is < 1 or > 65535 || uri.UserInfo.Length != 0 || uri.AbsolutePath != "/" ||
            uri.Query.Length != 0 || uri.Fragment.Length != 0 ||
            uri.HostNameType is not (UriHostNameType.Dns or UriHostNameType.IPv4))
            throw new ArgumentException("외부 주소를 https://도메인:외부포트 형식으로 입력하세요. 경로·쿼리는 넣지 마세요.");
        return new UriBuilder("https", uri.IdnHost.ToLowerInvariant(), uri.Port).Uri;
    }

    public X509Certificate2 LoadCertificate()
    {
        var origin = ParseOrigin(PublicOrigin);
        if (AccessToken is not { Length: 48 } || !AccessToken.All(Uri.IsHexDigit))
            throw new ArgumentException("외부 접속 링크가 올바르지 않습니다. 접속 링크를 새로 발급하세요.");
        if (string.IsNullOrWhiteSpace(CertificatePath) || !File.Exists(CertificatePath))
            throw new ArgumentException("개인 키가 포함된 HTTPS 인증서 파일(.pfx 또는 .p12)을 선택하세요.");
        X509Certificate2 certificate;
        try { certificate = new X509Certificate2(CertificatePath, CertificatePassword, X509KeyStorageFlags.UserKeySet); }
        catch (CryptographicException) { throw new ArgumentException("인증서를 열 수 없습니다. PFX 파일과 인증서 비밀번호를 확인하세요."); }
        try { ValidateCertificate(certificate, origin); return certificate; }
        catch { certificate.Dispose(); throw; }
    }

    public static void ValidateCertificate(X509Certificate2 certificate, Uri origin)
    {
        var now = DateTime.UtcNow;
        if (!certificate.HasPrivateKey) throw new ArgumentException("인증서에 서버용 개인 키가 없습니다. PFX 파일을 확인하세요.");
        if (now < certificate.NotBefore.ToUniversalTime() || now >= certificate.NotAfter.ToUniversalTime())
            throw new ArgumentException("인증서 유효 기간이 아닙니다. 갱신한 인증서와 PC 시각을 확인하세요.");
        if (!certificate.MatchesHostname(origin.IdnHost, allowWildcards: true, allowCommonName: false))
            throw new ArgumentException("인증서의 대상 도메인(SAN)이 외부 접속 주소와 일치하지 않습니다.");
        var usages = certificate.Extensions.OfType<X509EnhancedKeyUsageExtension>().ToArray();
        if (usages.Any(usage => !usage.EnhancedKeyUsages.Cast<Oid>().Any(oid => oid.Value == "1.3.6.1.5.5.7.3.1")))
            throw new ArgumentException("HTTPS 서버 인증용 인증서가 아닙니다.");
        if (certificate.Extensions.OfType<X509BasicConstraintsExtension>().Any(e => e.CertificateAuthority))
            throw new ArgumentException("CA 인증서 대신 서버 인증서를 선택하세요.");
    }
}

public sealed class MobileEndpointPolicy
{
    private readonly LanAddress _lan;
    public bool External { get; }
    public string Origin { get; }
    private readonly string _authority;
    private readonly bool _defaultPort;

    public MobileEndpointPolicy(LanAddress lan, int localPort, string? publicOrigin = null)
    {
        _lan = lan;
        External = publicOrigin is not null;
        var uri = External ? MobileConnectionOptions.ParseOrigin(publicOrigin!) : new Uri($"https://{lan.Address}:{localPort}");
        Origin = uri.GetLeftPart(UriPartial.Authority);
        _authority = uri.Authority;
        _defaultPort = uri.IsDefaultPort;
    }

    public bool Allows(IPAddress? peer, string host) => peer is not null &&
        (External || _lan.Contains(peer)) &&
        (string.Equals(host, _authority, StringComparison.OrdinalIgnoreCase) ||
         _defaultPort && string.Equals(host, _authority + ":443", StringComparison.OrdinalIgnoreCase));

    public bool AllowsOrigin(string origin) => string.Equals(origin, Origin, StringComparison.Ordinal);
}
