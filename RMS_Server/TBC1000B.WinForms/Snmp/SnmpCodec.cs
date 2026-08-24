using System.Buffers.Binary;
using System.Net;
using System.Text;

namespace TBC1000B.WinForms.Snmp;

public enum SnmpDataType : byte
{
    Integer = 0x02, OctetString = 0x04, Null = 0x05, ObjectIdentifier = 0x06,
    IpAddress = 0x40, Counter32 = 0x41, Gauge32 = 0x42, TimeTicks = 0x43,
    Opaque = 0x44, Counter64 = 0x46, NoSuchObject = 0x80, NoSuchInstance = 0x81, EndOfMibView = 0x82
}

public sealed record SnmpVariable(string Oid, SnmpDataType Type, object? Value)
{
    public string DisplayValue => Value switch
    {
        null => "",
        byte[] bytes => BitConverter.ToString(bytes).Replace("-", " "),
        _ => Convert.ToString(Value, System.Globalization.CultureInfo.InvariantCulture) ?? ""
    };
}

public sealed record SnmpMessage(int Version, string Community, byte PduType, int RequestId,
    int ErrorStatus, int ErrorIndex, IReadOnlyList<SnmpVariable> Variables);

public static class SnmpCodec
{
    public const byte GetRequest = 0xA0, GetNextRequest = 0xA1, Response = 0xA2, SetRequest = 0xA3, GetBulkRequest = 0xA5, TrapV2 = 0xA7;

    public static byte[] EncodeRequest(string community, byte pduType, int requestId,
        IReadOnlyList<SnmpVariable> variables, int errorStatus = 0, int errorIndex = 0)
    {
        var bindings = Sequence(variables.Select(v => Sequence(Oid(v.Oid), EncodeValue(v.Type, v.Value))).ToArray());
        var pdu = Tlv(pduType, Combine(Integer(requestId), Integer(errorStatus), Integer(errorIndex), bindings));
        return Sequence(Integer(1), Octets(Encoding.ASCII.GetBytes(community)), pdu);
    }

    public static SnmpMessage Decode(ReadOnlySpan<byte> packet)
    {
        var root = new BerReader(packet).ReadExpected(0x30); var message = new BerReader(root);
        var version = checked((int)ReadSigned(message.ReadExpected(0x02)));
        var community = Encoding.ASCII.GetString(message.ReadExpected(0x04));
        var pduItem = message.ReadItem();
        if (pduItem.Tag is not (Response or TrapV2 or GetRequest or GetNextRequest or SetRequest or GetBulkRequest)) throw new InvalidDataException($"지원하지 않는 SNMP PDU 0x{pduItem.Tag:X2}");
        var pdu = new BerReader(pduItem.Value); var requestId = checked((int)ReadSigned(pdu.ReadExpected(0x02)));
        var errorStatus = checked((int)ReadSigned(pdu.ReadExpected(0x02))); var errorIndex = checked((int)ReadSigned(pdu.ReadExpected(0x02)));
        var listReader = new BerReader(pdu.ReadExpected(0x30)); var variables = new List<SnmpVariable>();
        while (!listReader.End) { var binding = new BerReader(listReader.ReadExpected(0x30)); var oid = DecodeOid(binding.ReadExpected(0x06)); var value = binding.ReadItem(); variables.Add(new SnmpVariable(oid, (SnmpDataType)value.Tag, DecodeValue(value.Tag, value.Value))); }
        return new SnmpMessage(version, community, pduItem.Tag, requestId, errorStatus, errorIndex, variables);
    }

    private static object? DecodeValue(byte tag, ReadOnlySpan<byte> value) => tag switch
    {
        0x02 => ReadSigned(value),
        0x04 => DecodeText(value),
        0x05 or 0x80 or 0x81 or 0x82 => null,
        0x06 => DecodeOid(value),
        0x40 when value.Length == 4 => new IPAddress(value).ToString(),
        0x41 or 0x42 or 0x43 or 0x46 => ReadUnsigned(value),
        _ => value.ToArray()
    };

    private static object DecodeText(ReadOnlySpan<byte> value)
    {
        try { return new UTF8Encoding(false, true).GetString(value); } catch (DecoderFallbackException) { return value.ToArray(); }
    }

    private static byte[] EncodeValue(SnmpDataType type, object? value) => type switch
    {
        SnmpDataType.Null => Tlv((byte)type, []),
        SnmpDataType.Integer => Integer(Convert.ToInt64(value)),
        SnmpDataType.Counter32 or SnmpDataType.Gauge32 or SnmpDataType.TimeTicks or SnmpDataType.Counter64 => Unsigned((byte)type, Convert.ToUInt64(value)),
        SnmpDataType.OctetString => Octets(value is byte[] b ? b : Encoding.UTF8.GetBytes(Convert.ToString(value) ?? "")),
        SnmpDataType.ObjectIdentifier => Oid(Convert.ToString(value) ?? "0.0"),
        _ => throw new NotSupportedException($"SET 데이터 형식 {type}은 지원하지 않습니다.")
    };

    private static byte[] Sequence(params byte[][] parts) => Tlv(0x30, Combine(parts));
    private static byte[] Octets(byte[] value) => Tlv(0x04, value);
    private static byte[] Integer(long value)
    {
        Span<byte> temp = stackalloc byte[8]; BinaryPrimitives.WriteInt64BigEndian(temp, value); var start = 0;
        while (start < 7 && ((temp[start] == 0 && (temp[start + 1] & 0x80) == 0) || (temp[start] == 0xFF && (temp[start + 1] & 0x80) != 0))) start++;
        return Tlv(0x02, temp[start..].ToArray());
    }
    private static byte[] Unsigned(byte tag, ulong value)
    {
        Span<byte> temp = stackalloc byte[9]; BinaryPrimitives.WriteUInt64BigEndian(temp[1..], value); var start = 1; while (start < 8 && temp[start] == 0) start++; if ((temp[start] & 0x80) != 0) start--; return Tlv(tag, temp[start..].ToArray());
    }
    private static byte[] Oid(string oid)
    {
        var parts = oid.Trim('.').Split('.').Select(ulong.Parse).ToArray(); if (parts.Length < 2 || parts[0] > 2 || (parts[0] < 2 && parts[1] > 39)) throw new FormatException($"잘못된 OID: {oid}");
        var bytes = new List<byte>(); AppendBase128(bytes, parts[0] * 40 + parts[1]); for (var i = 2; i < parts.Length; i++) AppendBase128(bytes, parts[i]); return Tlv(0x06, bytes.ToArray());
    }
    private static void AppendBase128(List<byte> output, ulong value)
    {
        Span<byte> temp = stackalloc byte[10]; var index = temp.Length; temp[--index] = (byte)(value & 0x7F); while ((value >>= 7) > 0) temp[--index] = (byte)((value & 0x7F) | 0x80); output.AddRange(temp[index..].ToArray());
    }
    private static string DecodeOid(ReadOnlySpan<byte> value)
    {
        var values = new List<ulong>(); ulong current = 0; foreach (var b in value) { current = (current << 7) | (uint)(b & 0x7F); if ((b & 0x80) == 0) { values.Add(current); current = 0; } } if (current != 0 || values.Count == 0) throw new InvalidDataException("잘못된 OID BER입니다.");
        var first = values[0]; var firstArc = first < 40 ? 0UL : first < 80 ? 1UL : 2UL; var secondArc = first - firstArc * 40; return string.Join('.', new[] { firstArc, secondArc }.Concat(values.Skip(1)));
    }
    private static long ReadSigned(ReadOnlySpan<byte> value)
    {
        if (value.Length is 0 or > 8) throw new InvalidDataException("INTEGER 길이가 잘못되었습니다."); long result = (value[0] & 0x80) == 0 ? 0 : -1; foreach (var b in value) result = (result << 8) | b; return result;
    }
    private static ulong ReadUnsigned(ReadOnlySpan<byte> value)
    {
        if (value.Length > 9 || (value.Length == 9 && value[0] != 0)) throw new InvalidDataException("Unsigned INTEGER 길이가 잘못되었습니다."); ulong result = 0; foreach (var b in value[(value.Length == 9 ? 1 : 0)..]) result = (result << 8) | b; return result;
    }
    private static byte[] Tlv(byte tag, byte[] value) => Combine([tag], Length(value.Length), value);
    private static byte[] Length(int value)
    {
        if (value < 128) return [(byte)value]; Span<byte> temp = stackalloc byte[4]; BinaryPrimitives.WriteInt32BigEndian(temp, value); var start = 0; while (temp[start] == 0) start++; return [(byte)(0x80 | (4 - start)), .. temp[start..].ToArray()];
    }
    private static byte[] Combine(params byte[][] arrays) { var length = arrays.Sum(a => a.Length); var result = new byte[length]; var offset = 0; foreach (var a in arrays) { Buffer.BlockCopy(a, 0, result, offset, a.Length); offset += a.Length; } return result; }

    private ref struct BerReader
    {
        public readonly ref struct BerItem(byte tag, ReadOnlySpan<byte> value)
        {
            public byte Tag { get; } = tag;
            public ReadOnlySpan<byte> Value { get; } = value;
        }
        private ReadOnlySpan<byte> _source; private int _offset;
        public BerReader(ReadOnlySpan<byte> source) { _source = source; _offset = 0; }
        public bool End => _offset >= _source.Length;
        public BerItem ReadItem() { if (End) throw new EndOfStreamException(); var tag = _source[_offset++]; var length = ReadLength(); if (length < 0 || _offset + length > _source.Length) throw new InvalidDataException("BER 길이가 패킷 범위를 벗어납니다."); var value = _source.Slice(_offset, length); _offset += length; return new BerItem(tag, value); }
        public ReadOnlySpan<byte> ReadExpected(byte tag) { var item = ReadItem(); if (item.Tag != tag) throw new InvalidDataException($"BER 태그 0x{tag:X2} 대신 0x{item.Tag:X2}가 수신되었습니다."); return item.Value; }
        private int ReadLength() { if (_offset >= _source.Length) throw new EndOfStreamException(); var first = _source[_offset++]; if ((first & 0x80) == 0) return first; var count = first & 0x7F; if (count is 0 or > 4 || _offset + count > _source.Length) throw new InvalidDataException("지원하지 않는 BER 길이입니다."); var value = 0; for (var i = 0; i < count; i++) value = (value << 8) | _source[_offset++]; return value; }
    }
}
