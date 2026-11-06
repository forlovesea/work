using System.Reflection;
using System.Text;
using PCRemoteControl;
using PCRemoteControl.Watchdog;

static void Check(bool value, string name) { if (!value) throw new Exception(name); Console.WriteLine("PASS " + name); }
Check(Enumerable.Range(1, 7).Select(RecoveryPolicy.DelaySeconds).SequenceEqual(new[] { 5, 10, 20, 40, 60, 60, 60 }), "bounded restart backoff");
Check(!RecoveryPolicy.IsStale(59000, double.PositiveInfinity), "startup grace");
Check(!RecoveryPolicy.IsStale(120000, 2), "healthy UI retained");
Check(RecoveryPolicy.IsStale(120000, 61), "frozen UI detected");
Check(RecoveryPolicy.IsStale(120000, double.PositiveInfinity), "missing heartbeat detected");
var transform = typeof(TargetRecovery).GetMethod("Transform", BindingFlags.NonPublic | BindingFlags.Static)!;
byte[] plain = Encoding.UTF8.GetBytes("test-password-한글");
byte[] encrypted = (byte[])transform.Invoke(null, new object[] { plain, true })!;
Check(!encrypted.SequenceEqual(plain), "DPAPI encrypts password");
byte[] restored = (byte[])transform.Invoke(null, new object[] { encrypted, false })!;
Check(restored.SequenceEqual(plain), "DPAPI password roundtrip");
