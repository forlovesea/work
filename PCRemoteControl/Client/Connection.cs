using System.Buffers.Binary;
using System.Net.Security;
using System.Net.Sockets;
using System.Security.Authentication;
using System.Security.Cryptography.X509Certificates;
using System.Text.Json;

namespace PCRemoteControl;
sealed class LoginException(string message) : IOException(message);
sealed class RelayCertificateException(string message, Exception inner) : IOException(message, inner);

sealed class Connection : IDisposable
{
    readonly TcpClient tcp = new() { NoDelay = true };
    readonly SemaphoreSlim gate = new(1);
    SslStream stream = null!;
    public async Task Open(string host, int port, object hello, Func<CancellationToken, string?> requestCode, CancellationToken token)
    {
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(token);
        timeout.CancelAfter(TimeSpan.FromSeconds(15));
        await tcp.ConnectAsync(host, port, timeout.Token);
        string? certificateError = null;
        stream = new SslStream(tcp.GetStream(), false, (_, certificate, chain, errors) =>
        {
            if (errors == SslPolicyErrors.None) return true;
            var flags = chain?.ChainStatus.Aggregate(X509ChainStatusFlags.NoError, (value, item) => value | item.Status)
                ?? X509ChainStatusFlags.NoError;
            bool timeError = (flags & (X509ChainStatusFlags.NotTimeValid | X509ChainStatusFlags.NotTimeNested)) != 0;
            certificateError = timeError
                ? "Relay 인증서 유효기간 오류입니다. Windows 설정 → 시간 및 언어 → 날짜 및 시간에서 시간을 동기화하세요. 시간이 맞으면 서버 인증서 체인을 갱신하고 Relay를 재시작해야 합니다."
                : "Relay 인증서 검증 실패입니다. 서버 주소와 인증서의 이름·신뢰 체인을 확인하세요.";
            certificateError += $"\n이 PC 현재 시각(UTC): {DateTimeOffset.UtcNow:yyyy-MM-dd HH:mm:ss}";
            if (certificate != null)
            {
                using var cert = new X509Certificate2(certificate);
                certificateError += $"\n서버 인증서 유효기간(UTC): {cert.NotBefore.ToUniversalTime():yyyy-MM-dd HH:mm:ss} ~ {cert.NotAfter.ToUniversalTime():yyyy-MM-dd HH:mm:ss}";
            }
            certificateError += $"\n검증 결과: {errors} / {flags}\n자동 재연결을 중지했습니다. 조치 후 ‘서버 연결’을 누르세요.";
            return false;
        });
        try
        {
            await stream.AuthenticateAsClientAsync(new SslClientAuthenticationOptions { TargetHost = host }, timeout.Token);
        }
        catch (AuthenticationException ex) when (certificateError != null)
        {
            throw new RelayCertificateException(certificateError, ex);
        }
        await Send(hello, timeout.Token);
        var answer = await Read(token);
        if (answer.GetProperty("type").GetString() != "email_required")
            throw new LoginException(answer.TryGetProperty("message", out var error) ? error.GetString() ?? "인증 실패" : "이메일 인증을 지원하는 서버로 업데이트하세요.");
        using var verification = CancellationTokenSource.CreateLinkedTokenSource(token);
        verification.CancelAfter(TimeSpan.FromSeconds(295));
        var code = requestCode(verification.Token);
        if (code == null || verification.IsCancellationRequested)
            throw new LoginException("이메일 인증이 취소되었거나 만료되었습니다. 서버 연결을 다시 눌러주세요.");
        await Send(new { type = "verify_email", code }, verification.Token);
        answer = await Read(verification.Token);
        if (answer.GetProperty("type").GetString() != "ok")
            throw new LoginException(answer.GetProperty("message").GetString() ?? "이메일 인증 실패");
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
        try { await stream.ReadExactlyAsync(header, timeout.Token); }
        catch (EndOfStreamException ex)
        {
            throw new IOException("Relay 서버가 연결을 종료했습니다. 서버 로그와 HOST/TARGET 버전을 확인하세요.", ex);
        }
        int length = BinaryPrimitives.ReadInt32BigEndian(header);
        if (length <= 0 || length > 8 * 1024 * 1024) throw new IOException("Invalid message length");
        byte[] raw = new byte[length];
        await stream.ReadExactlyAsync(raw, timeout.Token);
        using var doc = JsonDocument.Parse(raw);
        return doc.RootElement.Clone();
    }
    public void Dispose() { tcp.Dispose(); stream?.Dispose(); }
}
