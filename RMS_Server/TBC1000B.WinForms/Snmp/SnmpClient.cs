using System.Net.Sockets;

namespace TBC1000B.WinForms.Snmp;

public sealed class SnmpClient
{
    private int _requestId = Environment.TickCount & 0x7FFFFFFF;
    public TimeSpan Timeout { get; init; } = TimeSpan.FromSeconds(2.5);
    public int Retries { get; init; } = 1;

    public Task<IReadOnlyList<SnmpVariable>> GetAsync(string address, int port, string community, IEnumerable<string> oids, CancellationToken token) =>
        SendAsync(address, port, community, SnmpCodec.GetRequest, oids.Select(o => new SnmpVariable(o, SnmpDataType.Null, null)).ToArray(), 0, 0, token);

    public Task<IReadOnlyList<SnmpVariable>> SetAsync(string address, int port, string community, params SnmpVariable[] values) =>
        SendAsync(address, port, community, SnmpCodec.SetRequest, values, 0, 0, CancellationToken.None);

    public async Task<IReadOnlyList<SnmpVariable>> WalkBulkAsync(string address, int port, string community, string baseOid, int maxRepetitions, CancellationToken token)
    {
        var result = new List<SnmpVariable>(); var cursor = baseOid;
        for (var page = 0; page < 100; page++)
        {
            var values = await SendAsync(address, port, community, SnmpCodec.GetBulkRequest, [new SnmpVariable(cursor, SnmpDataType.Null, null)], 0, maxRepetitions, token);
            var inTree = values.Where(v => IsChild(baseOid, v.Oid) && v.Type != SnmpDataType.EndOfMibView).ToArray();
            result.AddRange(inTree); if (inTree.Length == 0 || inTree.Length < values.Count || inTree[^1].Oid == cursor) break; cursor = inTree[^1].Oid;
        }
        return result;
    }

    private async Task<IReadOnlyList<SnmpVariable>> SendAsync(string address, int port, string community, byte pdu, IReadOnlyList<SnmpVariable> variables, int errorStatus, int errorIndex, CancellationToken token)
    {
        var requestId = Interlocked.Increment(ref _requestId) & 0x7FFFFFFF; var packet = SnmpCodec.EncodeRequest(community, pdu, requestId, variables, errorStatus, errorIndex);
        Exception? last = null;
        for (var attempt = 0; attempt <= Retries; attempt++)
        {
            token.ThrowIfCancellationRequested(); using var udp = new UdpClient();
            try
            {
                await udp.SendAsync(packet, packet.Length, address, port); using var timeout = CancellationTokenSource.CreateLinkedTokenSource(token); timeout.CancelAfter(Timeout);
                var received = await udp.ReceiveAsync(timeout.Token); var response = SnmpCodec.Decode(received.Buffer);
                if (response.PduType != SnmpCodec.Response || response.RequestId != requestId) throw new InvalidDataException("SNMP 응답 ID가 요청과 일치하지 않습니다.");
                if (!string.Equals(response.Community, community, StringComparison.Ordinal)) throw new InvalidDataException("SNMP community가 일치하지 않습니다.");
                if (response.ErrorStatus != 0) throw new SnmpException(response.ErrorStatus, response.ErrorIndex); return response.Variables;
            }
            catch (Exception ex) when (ex is SocketException or OperationCanceledException) { if (token.IsCancellationRequested) throw; last = ex; }
        }
        throw new TimeoutException($"SNMP 응답 시간 초과: {address}:{port}", last);
    }
    private static bool IsChild(string root, string oid) => oid.StartsWith(root.TrimEnd('.') + ".", StringComparison.Ordinal);
}

public sealed class SnmpException(int status, int index) : Exception($"SNMP 오류 상태 {status}, 인덱스 {index}")
{ public int Status { get; } = status; public int Index { get; } = index; }
