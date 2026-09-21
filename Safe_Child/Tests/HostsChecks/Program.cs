using SafeChild;

var checks = 0;
void Check(string text, bool expected, string state, bool matches)
{
    var actual = HostsStatus.Parse(text).Describe("example.com", expected);
    if (actual.Text != state || actual.Matches != matches)
        throw new Exception($"Expected {state}/{matches}, got {actual}");
    checks++;
}

Check("0.0.0.0 example.com\n0.0.0.0 www.example.com", true, "차단", true);
Check("# 0.0.0.0 example.com www.example.com", false, "해제", true);
Check("127.0.0.1\tEXAMPLE.COM. www.example.com # comment\r\n", true, "차단", true);
Check("::1 example.com\n:: www.example.com", true, "차단", true);
Check("::ffff:127.0.0.1 example.com www.example.com", true, "차단", true);
Check("0.0.0.0 example.com", true, "일부 차단 (설정 불일치)", false);
Check("0.0.0.0 www.example.com", false, "일부 차단 (설정 불일치)", false);
Check("0.0.0.0 example.com www.example.com", false, "차단 (설정 불일치)", false);
Check("", true, "해제 (설정 불일치)", false);
Check("0.0.0.0 otherexample.com\ninvalid example.com\n203.0.113.1 example.com", false, "해제", true);
Check("0.0.0.0 example.com www.example.com\n203.0.113.1 example.com", true, "충돌 확인 필요 (설정 불일치)", false);
Check("0.0.0.0 example.com www.example.com\n0.0.0.0 example.com", true, "차단", true);

var path = Path.Combine(Path.GetTempPath(), $"safechild-hosts-check-{Guid.NewGuid():N}");
try
{
    File.WriteAllText(path, "0.0.0.0 example.com www.example.com");
    if (!HostsStatus.Read(path).Describe("example.com", true).Matches) throw new Exception("File read failed");
    File.WriteAllText(path, "");
    if (!HostsStatus.Read(path).Describe("example.com", false).Matches) throw new Exception("External change not detected");
    File.Delete(path);
    var missing = HostsStatus.Read(path).Describe("example.com", false);
    if (missing.Text != "확인 실패" || missing.Matches) throw new Exception("Missing file reported as released");
    checks += 3;
}
finally { if (File.Exists(path)) File.Delete(path); }
Console.WriteLine($"PASS: {checks} hosts checks (parsing, aliases, IPv4/IPv6, conflicts, external changes, read failure)");
