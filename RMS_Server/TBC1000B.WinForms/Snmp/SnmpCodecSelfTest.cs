namespace TBC1000B.WinForms.Snmp;

internal static class SnmpCodecSelfTest
{
    public static void Run()
    {
        var variables = new[] {
            new SnmpVariable("1.3.6.1.2.1.1.3.0", SnmpDataType.TimeTicks, 123456UL),
            new SnmpVariable("1.3.6.1.6.3.1.1.4.1.0", SnmpDataType.ObjectIdentifier, "1.3.6.1.4.1.2011.6.164.0.1"),
            new SnmpVariable("1.3.6.1.2.1.1.1.0", SnmpDataType.OctetString, "TBC1000B") };
        var packet = SnmpCodec.EncodeRequest("test", SnmpCodec.Response, 739, variables);
        var decoded = SnmpCodec.Decode(packet);
        if (decoded.Version != 1 || decoded.Community != "test" || decoded.RequestId != 739 || decoded.Variables.Count != 3) throw new InvalidDataException("SNMP BER 자체 시험의 메시지 필드가 일치하지 않습니다.");
        if (decoded.Variables[0].Oid != variables[0].Oid || decoded.Variables[0].DisplayValue != "123456") throw new InvalidDataException("SNMP BER TimeTicks 시험 실패");
        if (decoded.Variables[1].DisplayValue != variables[1].Value?.ToString()) throw new InvalidDataException("SNMP BER OID 시험 실패");
        if (decoded.Variables[2].DisplayValue != "TBC1000B") throw new InvalidDataException("SNMP BER 문자열 시험 실패");
    }
}
