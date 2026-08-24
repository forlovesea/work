using System.Net;
using System.Net.Sockets;
using TBC1000B.WinForms.Snmp;
using TBC1000B.WinForms.Models;
using TBC1000B.WinForms.Services;
using System.IO.Compression;
using System.Xml.Linq;

if (args.Length == 2 && args[0] == "--device")
{
    var profilePath = Path.GetFullPath(args[1]); var profile = new ProfileStore(Path.GetDirectoryName(profilePath)!).Load(profilePath); var probe = new SnmpClient { Timeout = TimeSpan.FromSeconds(2.5), Retries = 1 };
    var response = await probe.GetAsync(profile.Address, profile.Port, profile.GetCommunity, ["1.3.6.1.2.1.1.3.0"], CancellationToken.None); var deviceRaw = new Dictionary<string, string>(StringComparer.Ordinal);
    await Task.Delay(500);
    foreach (var root in new[] { "1.3.6.1.4.1.2011.6.164.1.18.1", "1.3.6.1.4.1.2011.6.164.1.18.2", "1.3.6.1.4.1.2011.6.164.1.17.1", "1.3.6.1.4.1.2011.6.164.1.17.2", "1.3.6.1.4.1.2011.6.164.1.1.2.99" }) { var walked = await probe.WalkBulkAsync(profile.Address, profile.Port, profile.GetCommunity, root, 10, CancellationToken.None); foreach (var variable in walked) deviceRaw[variable.Oid] = variable.DisplayValue; Console.WriteLine($"  WALK {root}: {walked.Count}"); await Task.Delay(100); }
    var deviceSnapshot = new MonitorSnapshot(); SnmpDataMapper.Apply(deviceSnapshot, deviceRaw); var connectedModules = deviceSnapshot.Modules.Where(m => m.Connected).ToArray();
    Console.WriteLine($"DEVICE PASS: {profile.Address}:{profile.Port} sysUpTime={response.Single().DisplayValue}, OIDs={deviceRaw.Count}, modules={connectedModules.Length}"); foreach (var m in connectedModules) Console.WriteLine($"  #{m.Number:00} Equip={m.EquipmentId} V={m.Voltage:0.0} A={m.Current:0.0} State={m.Status} SOC={m.Soc} SOH={m.Soh}"); return;
}

var agent = new UdpClient(new IPEndPoint(IPAddress.Loopback, 0));
var endpoint = (IPEndPoint)agent.Client.LocalEndPoint!;
var agentTask = Task.Run(async () =>
{
    var requestPacket = await agent.ReceiveAsync();
    var request = SnmpCodec.Decode(requestPacket.Buffer);
    var response = SnmpCodec.EncodeRequest(request.Community, SnmpCodec.Response, request.RequestId,
        [new SnmpVariable("1.3.6.1.2.1.1.3.0", SnmpDataType.TimeTicks, 98765UL)]);
    await agent.SendAsync(response, response.Length, requestPacket.RemoteEndPoint);
});

var client = new SnmpClient { Timeout = TimeSpan.FromSeconds(1), Retries = 0 };
var values = await client.GetAsync("127.0.0.1", endpoint.Port, "community", ["1.3.6.1.2.1.1.3.0"], CancellationToken.None);
await agentTask;
if (values.Count != 1 || values[0].Oid != "1.3.6.1.2.1.1.3.0" || values[0].DisplayValue != "98765") throw new Exception("GET UDP 왕복 검증 실패");

var setAgentTask = Task.Run(async () =>
{
    var requestPacket = await agent.ReceiveAsync(); var request = SnmpCodec.Decode(requestPacket.Buffer);
    if (request.PduType != SnmpCodec.SetRequest || request.Variables.Count != 1 || request.Variables[0].DisplayValue != "2") throw new Exception("SET 요청 검증 실패");
    var response = SnmpCodec.EncodeRequest(request.Community, SnmpCodec.Response, request.RequestId, request.Variables);
    await agent.SendAsync(response, response.Length, requestPacket.RemoteEndPoint);
});
var setValues = await client.SetAsync("127.0.0.1", endpoint.Port, "community", new SnmpVariable("1.3.6.1.4.1.2011.6.164.1.18.3.1.2.1", SnmpDataType.Integer, 2));
await setAgentTask;
if (setValues.Count != 1 || setValues[0].DisplayValue != "2") throw new Exception("SET UDP 왕복 검증 실패");

const int trapPort = 21620;
await using var receiver = new SnmpTrapReceiver();
using var trapCancel = new CancellationTokenSource();
var received = new TaskCompletionSource<SnmpMessage>(TaskCreationOptions.RunContinuationsAsynchronously);
receiver.MessageReceived += (_, data) => received.TrySetResult(data.Message);
var receiverTask = receiver.RunAsync(trapPort, "community", trapCancel.Token);
await Task.Delay(100);
using var sender = new UdpClient();
var trap = SnmpCodec.EncodeRequest("community", SnmpCodec.TrapV2, 55,
    [new SnmpVariable("1.3.6.1.6.3.1.1.4.1.0", SnmpDataType.ObjectIdentifier, "1.3.6.1.4.1.2011.6.164.0.1")]);
await sender.SendAsync(trap, trap.Length, "127.0.0.1", trapPort);
var trapMessage = await received.Task.WaitAsync(TimeSpan.FromSeconds(2));
if (trapMessage.PduType != SnmpCodec.TrapV2 || trapMessage.Variables.Count != 1) throw new Exception("Trap UDP 수신 검증 실패");
trapCancel.Cancel(); await receiverTask;

var snapshot = new MonitorSnapshot();
var raw = new Dictionary<string, string> {
    ["1.3.6.1.4.1.2011.6.164.1.17.1.1.5.96"] = "575",
    ["1.3.6.1.4.1.2011.6.164.1.17.1.1.6.96"] = "-23",
    ["1.3.6.1.4.1.2011.6.164.1.17.1.1.7.96"] = "10000",
    ["1.3.6.1.4.1.2011.6.164.1.17.1.1.8.96"] = "88",
    ["1.3.6.1.4.1.2011.6.164.1.17.1.1.13.96"] = "97",
    ["1.3.6.1.4.1.2011.6.164.1.17.1.1.23.96"] = "42",
    ["1.3.6.1.4.1.2011.6.164.1.17.2.1.13.96"] = "75",
    ["1.3.6.1.4.1.2011.6.164.1.17.2.1.30.96"] = "95",
    ["1.3.6.1.4.1.2011.6.164.1.18.1.1.2.1"] = "31001",
    ["1.3.6.1.4.1.2011.6.164.1.18.1.1.4.1"] = "1",
    ["1.3.6.1.4.1.2011.6.164.1.18.1.1.5.1"] = "V126",
    ["1.3.6.1.4.1.2011.6.164.1.18.1.1.12.1"] = "ESM-48100C1",
    ["1.3.6.1.4.1.2011.6.164.1.18.1.1.13.1"] = "UB74300131001",
    ["1.3.6.1.4.1.2011.6.164.1.18.2.1.1.1"] = "570",
    ["1.3.6.1.4.1.2011.6.164.1.18.2.1.2.1"] = "9",
    ["1.3.6.1.4.1.2011.6.164.1.18.2.1.3.1"] = "4",
    ["1.3.6.1.4.1.2011.6.164.1.18.2.1.4.1"] = "95",
    ["1.3.6.1.4.1.2011.6.164.1.18.2.1.6.1"] = "304",
    ["1.3.6.1.4.1.2011.6.164.1.18.2.1.22.1"] = "253",
    ["1.3.6.1.4.1.2011.6.164.1.18.2.1.52.1"] = "100",
    ["1.3.6.1.4.1.2011.6.164.1.1.2.99.1.2.77"] = "Cell 1 Fault",
    ["1.3.6.1.4.1.2011.6.164.1.1.2.99.1.3.77"] = "1",
    ["1.3.6.1.4.1.2011.6.164.1.1.2.99.1.5.77"] = "2026-08-24 10:00:00",
    ["1.3.6.1.4.1.2011.6.164.1.1.2.99.1.10.77"] = "1" };
foreach (var item in raw) snapshot.RawValues[item.Key] = item.Value;
SnmpDataMapper.Apply(snapshot, raw);
var module = snapshot.Modules[0];
if (module.EquipmentId != "31001" || module.Voltage != 57.0 || module.Current != 0.9 || module.Status != "충전중" || module.CellVoltages[0] != 3.04 || module.CellTemperatures[0] != 25.3 || module.Soc != 100) throw new Exception("Huawei MIB 매핑 검증 실패");
if (snapshot.ActiveAlarms.Count != 1 || module.Alarm != AlarmLevel.Critical || snapshot.Faults.Count != 1 || snapshot.Faults[0].CellNo != 1 || snapshot.Faults[0].Voltage != 3.04) throw new Exception("Active Alarm/Fault 매핑 검증 실패");
var summaryValues = SystemSummaryService.Create(snapshot);
if (summaryValues.Values["Rack 전압[V]"] != "57.5" || summaryValues.Values["SOC 충전율[%]"] != "88" || summaryValues.Values["Rack 전류[A]"] != "-2.3" || summaryValues.Values["방전 횟수"] != "42" || summaryValues.Values["Max 전압[V]"] != "57.0" || summaryValues.Values["Max 온도[℃]"] != "25.3" || summaryValues.Values["충전전류제한[C]"] != "0.75" || summaryValues.Values["SOC충전제한[%]"] != "95") throw new Exception("System summary OID/value mapping failed");
if (summaryValues.Title != "시스템 요약 정보 (Rack 전체용량: 1000Ah, SOH: 97%)") throw new Exception("System summary title mapping failed");
if (new[] { "과전압 충전차단", "고온 충전차단", "과전류 충전차단", "차단기 OFF" }.Any(label => summaryValues.Values[label] != "정상")) throw new Exception("System summary normal protection state failed");
snapshot.ActiveAlarms.Add(new ActiveAlarmEntry("Charge High Temperature Protection", AlarmLevel.Major, "2026-08-24 10:01:00", 1, "1"));
snapshot.ActiveAlarms.Add(new ActiveAlarmEntry("Battery Fuse Broken", AlarmLevel.Critical, "2026-08-24 10:02:00", 1, "1"));
var abnormalSummary = SystemSummaryService.Create(snapshot);
if (abnormalSummary.Values["고온 충전차단"] != "비정상" || abnormalSummary.Values["차단기 OFF"] != "비정상" || abnormalSummary.Values["과전압 충전차단"] != "정상" || abnormalSummary.Values["과전류 충전차단"] != "정상") throw new Exception("System summary abnormal protection state failed");
snapshot.ActiveAlarms.RemoveRange(snapshot.ActiveAlarms.Count - 2, 2);

var trapLogRoot = Path.Combine(AppContext.BaseDirectory, "trap-log-smoke");
var trapLogger = new TrapLogService(trapLogRoot, Path.Combine("profiles", $"site-rack-{Guid.NewGuid():N}.ini"));
var trapLogPath = trapLogger.Append(new TrapEntry(new DateTime(2026, 8, 24, 12, 34, 56, 789), "1.2.3", "77", "Cell\tFault\nDetail", AlarmLevel.Critical, "31001", "ESM", "Controller"));
trapLogger.Append(new TrapEntry(new DateTime(2026, 8, 24, 12, 35, 0), "1.2.4", "78", "Resume", AlarmLevel.Normal, "31001", "ESM", "Controller", true));
var trapLogLines = File.ReadAllLines(trapLogPath);
if (trapLogLines.Length != 3 || !trapLogLines[0].StartsWith("Time\tTrapOid", StringComparison.Ordinal) || !trapLogLines[1].Contains("Cell\\tFault\\nDetail", StringComparison.Ordinal) || !trapLogLines[2].EndsWith("\t1", StringComparison.Ordinal)) throw new Exception("Trap daily log validation failed");

snapshot.Connection = ConnectionState.Connected;
var fields = OperationRecordService.FieldSpecs.Select(s => s.Key).ToHashSet();
var headers = OperationRecordService.CreateHeaders(fields); var recordRows = OperationRecordService.CreateRows(snapshot, new DateTime(2026, 8, 21, 11, 30, 0), fields);
var xlsxPath = Path.Combine(AppContext.BaseDirectory, "operation-record-smoke.xlsx"); SimpleXlsxWriter.Write(xlsxPath, headers, recordRows);
using (var xlsx = ZipFile.OpenRead(xlsxPath))
{
    var required = new[] { "[Content_Types].xml", "_rels/.rels", "xl/workbook.xml", "xl/_rels/workbook.xml.rels", "xl/styles.xml", "xl/worksheets/sheet1.xml" };
    if (required.Any(name => xlsx.GetEntry(name) is null)) throw new Exception("XLSX 필수 구성요소 검증 실패");
    using var sheetStream = xlsx.GetEntry("xl/worksheets/sheet1.xml")!.Open(); var sheet = XDocument.Load(sheetStream); XNamespace ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main";
    if (sheet.Descendants(ns + "row").Count() != 2 || sheet.Descendants(ns + "autoFilter").SingleOrDefault() is null || !sheet.Descendants(ns + "t").Any(e => e.Value == "기록시각") || !sheet.Descendants(ns + "t").Any(e => e.Value == "충전중")) throw new Exception("XLSX 내용 검증 실패");
}

using var slaveTestCancel = new CancellationTokenSource(); await using var masterCoordinator = new SlaveCoordinator(); await using var slaveCoordinator = new SlaveCoordinator();
masterCoordinator.StartMaster(slaveTestCancel.Token); var forwarded = new TaskCompletionSource<IReadOnlyDictionary<string, string>>(TaskCreationOptions.RunContinuationsAsynchronously); slaveCoordinator.ForwardedTrapReceived += (_, payload) => forwarded.TrySetResult(payload);
var assignedPort = slaveCoordinator.StartSlave("10.0.0.3", 0, "slave-test.ini", "Rack#Slave", slaveTestCancel.Token); await Task.Delay(250);
var status = masterCoordinator.GetStatuses().SingleOrDefault(); if (status is null || !status.IsAlive || status.Port != assignedPort || status.TargetIp != "10.0.0.3") throw new Exception("Slave 등록 검증 실패");
var forwardedPayload = new Dictionary<string, string> { ["_source_ip"] = "10.0.0.3", ["1.3.6.1.6.3.1.1.4.1.0"] = "1.3.6.1.4.1.2011.6.164.2.1.3.0.99" };
var deliveries = await masterCoordinator.ForwardAsync(forwardedPayload); if (deliveries.Count != 1) throw new Exception("Master Trap 전달 대상 검증 실패"); var receivedForward = await forwarded.Task.WaitAsync(TimeSpan.FromSeconds(2)); if (receivedForward["_source_ip"] != "10.0.0.3") throw new Exception("Slave Trap JSON 수신 검증 실패");
var noDeliveries = await masterCoordinator.ForwardAsync(new Dictionary<string, string> { ["_source_ip"] = "10.0.0.4" }); if (noDeliveries.Count != 0) throw new Exception("Slave 장비 IP 필터 검증 실패");
slaveCoordinator.Stop(); await Task.Delay(150); if (masterCoordinator.GetStatuses().Count != 0) throw new Exception("Slave 등록 해제 검증 실패"); slaveTestCancel.Cancel();
masterCoordinator.Stop();
using (var releasedMasterPort = new UdpClient(new IPEndPoint(IPAddress.Any, SlaveCoordinator.RegistrationPort))) { }
using (var releasedSlavePort = new UdpClient(new IPEndPoint(IPAddress.Loopback, assignedPort))) { }

using var controlAgent = new UdpClient(new IPEndPoint(IPAddress.Loopback, 0)); var controlEndpoint = (IPEndPoint)controlAgent.Client.LocalEndPoint!; using var controlCancel = new CancellationTokenSource();
var controlValues = new Dictionary<string, (SnmpDataType Type, long Value)> {
    ["1.3.6.1.2.1.1.3.0"] = (SnmpDataType.TimeTicks, 1234), ["1.3.6.1.4.1.2011.6.164.1.17.2.1.13.96"] = (SnmpDataType.Gauge32, 50),
    ["1.3.6.1.4.1.2011.6.164.1.17.2.1.29.96"] = (SnmpDataType.Integer, 1), ["1.3.6.1.4.1.2011.6.164.1.17.2.1.30.96"] = (SnmpDataType.Gauge32, 90), ["1.3.6.1.4.1.2011.6.164.1.1.2.4.0"] = (SnmpDataType.Integer, 0) };
var controlSetHistory = new System.Collections.Concurrent.ConcurrentQueue<(string Oid, long Value)>();
var controlAgentTask = Task.Run(async () =>
{
    while (!controlCancel.IsCancellationRequested) try
    {
        var packet = await controlAgent.ReceiveAsync(controlCancel.Token); var request = SnmpCodec.Decode(packet.Buffer); SnmpVariable[] responseVariables;
        if (request.PduType == SnmpCodec.SetRequest) { foreach (var variable in request.Variables) { var parsed = long.Parse(variable.DisplayValue); controlValues[variable.Oid] = (variable.Type, parsed); controlSetHistory.Enqueue((variable.Oid, parsed)); } responseVariables = request.Variables.ToArray(); }
        else if (request.PduType == SnmpCodec.GetBulkRequest && request.Variables[0].Oid == "1.3.6.1.4.1.2011.6.164.1.18.1") responseVariables = [new SnmpVariable("1.3.6.1.4.1.2011.6.164.1.18.1.1.2.1", SnmpDataType.OctetString, "31001"), new SnmpVariable("1.3.6.1.4.1.2011.6.164.1.18.1.1.4.1", SnmpDataType.Integer, 1)];
        else if (request.PduType == SnmpCodec.GetBulkRequest && request.Variables[0].Oid == "1.3.6.1.4.1.2011.6.164.1.18.2") responseVariables = [new SnmpVariable("1.3.6.1.4.1.2011.6.164.1.18.2.1.3.1", SnmpDataType.Integer, 4)];
        else if (request.PduType == SnmpCodec.GetBulkRequest) responseVariables = [new SnmpVariable("1.3.6.1.6.3.999.0", SnmpDataType.Null, null)];
        else responseVariables = request.Variables.Select(v => controlValues.TryGetValue(v.Oid, out var stored) ? new SnmpVariable(v.Oid, stored.Type, stored.Value) : new SnmpVariable(v.Oid, SnmpDataType.Null, null)).ToArray();
        var responsePacket = SnmpCodec.EncodeRequest(request.Community, SnmpCodec.Response, request.RequestId, responseVariables); await controlAgent.SendAsync(responsePacket, responsePacket.Length, packet.RemoteEndPoint);
    } catch (OperationCanceledException) when (controlCancel.IsCancellationRequested) { break; }
});
await using (var controlService = new SnmpMonitorService())
{
    var successfulPollSnapshots = 0;
    controlService.SnapshotChanged += (_, state) => { if (state.Connection == ConnectionState.Connected && state.ConsecutiveFailures == 0) Interlocked.Increment(ref successfulPollSnapshots); };
    using var trapPortProbe = new UdpClient(new IPEndPoint(IPAddress.Loopback, 0)); var reconnectTrapPort = ((IPEndPoint)trapPortProbe.Client.LocalEndPoint!).Port; trapPortProbe.Dispose();
    var reconnectOptions = new ConnectionOptions("127.0.0.1", controlEndpoint.Port, "read", "write", "trap", reconnectTrapPort, true);
    await controlService.ConnectAsync(reconnectOptions, CancellationToken.None);
    await controlService.SetChargeLimitAsync(75, CancellationToken.None); if (await controlService.GetChargeLimitAsync(CancellationToken.None) != 75) throw new Exception("충전전류 제한 서비스 검증 실패");
    await controlService.SetSocChargeLimitAsync(2, 95, CancellationToken.None); if (await controlService.GetSocChargeLimitAsync(CancellationToken.None) != (2, 95)) throw new Exception("SOC 제한 서비스 검증 실패");
    await controlService.SetSocChargeLimitAsync(1, null, CancellationToken.None); if ((await controlService.GetSocChargeLimitAsync(CancellationToken.None)).Enabled != 1) throw new Exception("SOC 미사용 서비스 검증 실패");
    await controlService.RequestTrapRetransmissionAsync(CancellationToken.None); if (controlValues["1.3.6.1.4.1.2011.6.164.1.1.2.4.0"].Value != 1) throw new Exception("Trap 재전송 서비스 검증 실패");
    await controlService.DisconnectAsync();
    using (var releasedTrapPort = new UdpClient(new IPEndPoint(IPAddress.Any, reconnectTrapPort))) { }
    await controlService.ConnectAsync(reconnectOptions, CancellationToken.None);
    await Task.Delay(TimeSpan.FromSeconds(5));
    if (Volatile.Read(ref successfulPollSnapshots) < 2) throw new Exception("Repeated polling soak validation failed");
    await controlService.SetEpoAsync(1, true, CancellationToken.None);
    await controlService.SetEpoAsync(1, false, CancellationToken.None);
    var epoHistory = controlSetHistory.ToArray();
    if (!epoHistory.Contains(("1.3.6.1.4.1.2011.6.164.1.2.2.1.1.11.1", 1)) || !epoHistory.Contains(("1.3.6.1.4.1.2011.6.164.1.18.3.1.2.1", 2)) || !epoHistory.Contains(("1.3.6.1.4.1.2011.6.164.1.18.3.1.2.1", 1))) throw new Exception("EPO prepare/cutoff/restore SNMP SET sequence failed");
    await controlService.DisconnectAsync();
    using (var releasedTrapPortAgain = new UdpClient(new IPEndPoint(IPAddress.Any, reconnectTrapPort))) { }
}
controlCancel.Cancel(); await controlAgentTask;
var profileTestDir = Path.Combine(AppContext.BaseDirectory, "profile-smoke"); var profileStore = new ProfileStore(profileTestDir); var profileTest = profileStore.Create("시험장소", "Rack_Test"); profileTest.ModuleOrder = [2, 4, 0, 1, 0, 0, 0, 0, 0, 0]; profileTest.ModuleBarcodes[2] = "SERIAL-002"; profileTest.AlarmVolume = 3; profileTest.AlarmLevels[4] = true; profileStore.Save(profileTest); var loadedProfile = profileStore.Load(profileTest.FilePath);
if (!loadedProfile.ModuleOrder.SequenceEqual(new[] { 2, 4, 0, 1, 0, 0, 0, 0, 0, 0 }) || loadedProfile.ModuleBarcodes.GetValueOrDefault(2) != "SERIAL-002" || loadedProfile.AlarmVolume != 3 || !loadedProfile.AlarmLevels[4]) throw new Exception("프로파일 설치순서/바코드/경보 설정 검증 실패");
Console.WriteLine("PASS: SNMP GET/SET, control OIDs, Trap/Fault, Huawei MIB, XLSX, profiles, and Master/Slave smoke tests");
