using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Text.Json;
using SIPSorcery.Media;
using SIPSorcery.Net;
using SIPSorceryMedia.Abstractions;
using SIPSorceryMedia.FFmpeg;

namespace PCRemoteControl;

sealed class WebRtcSession : IDisposable
{
    sealed class IceServerSettings
    {
        public string Urls { get; set; } = "";
        public string? Username { get; set; }
        public string? Credential { get; set; }
    }

    static readonly JsonSerializerOptions SignalJson = new() { IncludeFields = true, PropertyNameCaseInsensitive = true };
    readonly bool target;
    readonly Func<object, Task> sendSignal;
    readonly RTCPeerConnection peer;
    readonly FFmpegVideoEndPoint video;
    readonly object candidateGate = new();
    readonly Queue<object> pendingLocalCandidates = new();
    readonly Queue<RTCIceCandidateInit> pendingRemoteCandidates = new();
    string? sessionId;
    bool localDescriptionSent;
    bool remoteDescriptionSet;
    bool disposed;

    public event Action<Bitmap>? FrameReceived;
    public event Action<string>? StatusChanged;
    public event Action<Exception>? Failed;
    public bool IsConnected => !disposed && peer.connectionState == RTCPeerConnectionState.connected;

    public WebRtcSession(bool target, string? sessionId, Func<object, Task> sendSignal)
    {
        if (!FFmpegInit.EnsureBinariesRegistered())
            throw new IOException("FFmpeg 8.1 Shared 라이브러리를 찾을 수 없습니다. README의 FFmpeg 설치 안내를 확인하세요.");

        this.target = target;
        this.sessionId = sessionId;
        this.sendSignal = sendSignal;
        video = new FFmpegVideoEndPoint();
        video.RestrictFormats(format => format.Codec == VideoCodecsEnum.VP8);
        peer = new RTCPeerConnection(new RTCConfiguration { iceServers = LoadIceServers() });
        peer.onicecandidate += OnIceCandidate;
        peer.onconnectionstatechange += state =>
        {
            if (state == RTCPeerConnectionState.connected)
                StatusChanged?.Invoke("WebRTC 미디어 연결됨");
            else if (state == RTCPeerConnectionState.failed)
            {
                StatusChanged?.Invoke($"WebRTC 미디어 상태: {state}");
                Failed?.Invoke(new IOException("WebRTC 미디어 경로가 실패했습니다. ICE/TURN 설정과 네트워크를 확인하세요."));
            }
            else if (state == RTCPeerConnectionState.disconnected)
            {
                StatusChanged?.Invoke($"WebRTC 미디어 상태: {state}");
                Failed?.Invoke(new IOException("WebRTC 미디어 연결이 끊겼습니다."));
            }
        };
        video.OnVideoSourceError += error => Failed?.Invoke(new IOException(error));

        if (target)
        {
            peer.addTrack(new MediaStreamTrack(video.GetVideoSourceFormats(), MediaStreamStatusEnum.SendOnly));
            video.OnVideoSourceEncodedSample += peer.SendVideo;
            peer.OnVideoFormatsNegotiated += SetSourceFormat;
        }
        else
        {
            peer.addTrack(new MediaStreamTrack(video.GetVideoSinkFormats(), MediaStreamStatusEnum.RecvOnly));
            peer.OnVideoFormatsNegotiated += SetSinkFormat;
            peer.OnVideoFrameReceived += (remote, timestamp, frame, format) =>
                video.GotVideoFrame(remote, timestamp, frame, format);
            video.OnVideoSinkDecodedSampleFaster += OnVideoDecoded;
        }
    }

    static List<RTCIceServer> LoadIceServers() =>
        ParseIceServers(Environment.GetEnvironmentVariable("PCREMOTE_ICE_SERVERS"));

    internal static List<RTCIceServer> ParseIceServers(string? configured)
    {
        if (configured?.Length > 16 * 1024)
            throw new IOException("PCREMOTE_ICE_SERVERS가 허용 크기를 초과했습니다.");

        IceServerSettings?[] servers;
        if (string.IsNullOrWhiteSpace(configured))
        {
            servers = new[] { new IceServerSettings { Urls = "stun:stun.cloudflare.com:3478" } };
        }
        else
        {
            try
            {
                servers = JsonSerializer.Deserialize<IceServerSettings[]>(configured, SignalJson)
                    ?? throw new JsonException("ICE 서버 목록이 비어 있습니다.");
            }
            catch (JsonException ex)
            {
                throw new IOException("PCREMOTE_ICE_SERVERS 형식이 올바르지 않습니다.", ex);
            }
        }

        if (servers.Length == 0 || servers.Length > 16)
            throw new IOException("ICE 서버는 1~16개까지 설정할 수 있습니다.");

        var result = new List<RTCIceServer>(servers.Length);
        foreach (var server in servers)
        {
            if (server == null || string.IsNullOrWhiteSpace(server.Urls) || server.Urls.Length > 2048 ||
                !(server.Urls.StartsWith("stun:", StringComparison.OrdinalIgnoreCase) ||
                  server.Urls.StartsWith("turn:", StringComparison.OrdinalIgnoreCase) ||
                  server.Urls.StartsWith("turns:", StringComparison.OrdinalIgnoreCase)) ||
                (string.IsNullOrEmpty(server.Username) != string.IsNullOrEmpty(server.Credential)) ||
                server.Username?.Length > 512 || server.Credential?.Length > 512)
                throw new IOException("ICE 서버는 유효한 stun:/turn:/turns: URL과 TURN 사용자명·비밀번호 쌍을 사용해야 합니다.");

            result.Add(new RTCIceServer
            {
                urls = server.Urls,
                username = server.Username,
                credential = server.Credential
            });
        }
        return result;
    }

    void SetSourceFormat(List<VideoFormat> formats)
    {
        if (formats.Count == 0)
        {
            Failed?.Invoke(new IOException("WebRTC에서 공통 VP8 송신 형식을 협상하지 못했습니다."));
            return;
        }
        video.SetVideoSourceFormat(formats[0]);
    }

    void SetSinkFormat(List<VideoFormat> formats)
    {
        if (formats.Count == 0)
        {
            Failed?.Invoke(new IOException("WebRTC에서 공통 VP8 수신 형식을 협상하지 못했습니다."));
            return;
        }
        video.SetVideoSinkFormat(formats[0]);
    }

    public async Task CreateOffer()
    {
        if (target || string.IsNullOrWhiteSpace(sessionId))
            throw new InvalidOperationException("HOST만 유효한 세션 ID로 WebRTC Offer를 시작할 수 있습니다.");

        var offer = peer.createOffer(null);
        await peer.setLocalDescription(offer);
        await PublishLocalDescription("offer", peer.localDescription.sdp.ToString());
    }

    public async Task HandleSignal(JsonElement message)
    {
        string action = message.GetProperty("action").GetString() ?? "";
        string incomingSession = message.GetProperty("session").GetString() ?? "";
        if (incomingSession.Length != 32 || !Guid.TryParseExact(incomingSession, "N", out _))
            throw new IOException("WebRTC 신호의 세션 ID가 올바르지 않습니다.");

        if (sessionId == null && target && action == "offer")
            sessionId = incomingSession;
        if (!string.Equals(sessionId, incomingSession, StringComparison.Ordinal))
            return;

        switch (action)
        {
            case "offer" when target:
                ApplyRemoteDescription(RTCSdpType.offer, message.GetProperty("description").GetString());
                var answer = peer.createAnswer(null);
                await peer.setLocalDescription(answer);
                await PublishLocalDescription("answer", peer.localDescription.sdp.ToString());
                break;
            case "answer" when !target:
                ApplyRemoteDescription(RTCSdpType.answer, message.GetProperty("description").GetString());
                break;
            case "candidate":
                var candidate = JsonSerializer.Deserialize<RTCIceCandidateInit>(
                    message.GetProperty("candidate").GetRawText(), SignalJson)
                    ?? throw new IOException("WebRTC ICE candidate가 비어 있습니다.");
                if (remoteDescriptionSet)
                    peer.addIceCandidate(candidate);
                else
                    pendingRemoteCandidates.Enqueue(candidate);
                break;
            default:
                throw new IOException("현재 역할에서 허용되지 않는 WebRTC 신호입니다.");
        }
    }

    void ApplyRemoteDescription(RTCSdpType type, string? sdp)
    {
        if (string.IsNullOrWhiteSpace(sdp) || sdp.Length > 128 * 1024)
            throw new IOException("WebRTC SDP가 비어 있거나 크기 제한을 초과했습니다.");
        var result = peer.setRemoteDescription(new RTCSessionDescriptionInit { type = type, sdp = sdp });
        if (result != SetDescriptionResultEnum.OK)
            throw new IOException("WebRTC SDP 협상 실패: " + result);

        remoteDescriptionSet = true;
        while (pendingRemoteCandidates.Count > 0)
            peer.addIceCandidate(pendingRemoteCandidates.Dequeue());
    }

    void OnIceCandidate(RTCIceCandidate? candidate)
    {
        if (disposed || candidate == null || string.IsNullOrWhiteSpace(candidate.candidate))
            return;

        object value = new
        {
            candidate = candidate.candidate,
            sdpMid = candidate.sdpMid,
            sdpMLineIndex = candidate.sdpMLineIndex
        };
        lock (candidateGate)
        {
            if (!localDescriptionSent)
            {
                pendingLocalCandidates.Enqueue(value);
                return;
            }
        }
        _ = SendCandidateFromEvent(value);
    }

    async Task PublishLocalDescription(string action, string description)
    {
        string id = sessionId ?? throw new IOException("WebRTC 세션 ID가 설정되지 않았습니다.");
        await sendSignal(new { type = "rtc", action, session = id, description });
        object[] candidates;
        lock (candidateGate)
        {
            localDescriptionSent = true;
            candidates = pendingLocalCandidates.ToArray();
            pendingLocalCandidates.Clear();
        }
        foreach (object candidate in candidates)
            await SendCandidate(id, candidate);
    }

    Task SendCandidate(object candidate) =>
        sessionId == null ? Task.CompletedTask : SendCandidate(sessionId, candidate);

    Task SendCandidate(string id, object candidate) =>
        disposed ? Task.CompletedTask : sendSignal(new { type = "rtc", action = "candidate", session = id, candidate });

    async Task SendCandidateFromEvent(object candidate)
    {
        try
        {
            if (sessionId != null)
                await SendCandidate(sessionId, candidate);
        }
        catch (Exception ex) when (!disposed)
        {
            Failed?.Invoke(ex);
        }
    }

    public void SendFrame(RawVideoFrame frame)
    {
        if (!target || !IsConnected)
            return;
        video.ExternalVideoSourceRawSample(50, frame.Width, frame.Height, frame.Data, VideoPixelFormatsEnum.Bgr);
    }

    void OnVideoDecoded(RawImage image)
    {
        try
        {
            if (image.PixelFormat != VideoPixelFormatsEnum.Bgr || image.Width <= 0 || image.Height <= 0 ||
                (long)image.Width * image.Height > 40_000_000 || image.Stride <= 0 ||
                image.Width > int.MaxValue / 3 || image.Stride < image.Width * 3)
                throw new IOException("수신 비디오 픽셀 형식이나 크기가 올바르지 않습니다.");

            var bitmap = new Bitmap(image.Width, image.Height, PixelFormat.Format24bppRgb);
            var data = bitmap.LockBits(new Rectangle(0, 0, bitmap.Width, bitmap.Height),
                ImageLockMode.WriteOnly, PixelFormat.Format24bppRgb);
            try { image.CopyTo(data.Scan0, data.Stride); }
            finally { bitmap.UnlockBits(data); }
            FrameReceived?.Invoke(bitmap);
        }
        catch (Exception ex) when (ex is IOException or ArgumentException or InvalidOperationException or ExternalException or OverflowException)
        {
            Failed?.Invoke(ex);
        }
    }

    public void Dispose()
    {
        if (disposed) return;
        disposed = true;
        peer.close();
        video.Dispose();
    }
}
