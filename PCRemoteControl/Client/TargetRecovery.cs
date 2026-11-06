using System.Runtime.InteropServices;
using System.Text;

namespace PCRemoteControl;
static class TargetRecovery
{
    [StructLayout(LayoutKind.Sequential)] struct Blob { public int size; public IntPtr data; }
    [DllImport("crypt32.dll", SetLastError = true)] static extern bool CryptProtectData(ref Blob input, string? description, IntPtr entropy, IntPtr reserved, IntPtr prompt, uint flags, out Blob output);
    [DllImport("crypt32.dll", SetLastError = true)] static extern bool CryptUnprotectData(ref Blob input, IntPtr description, IntPtr entropy, IntPtr reserved, IntPtr prompt, uint flags, out Blob output);
    [DllImport("kernel32.dll")] static extern IntPtr LocalFree(IntPtr memory);
    static string FilePath => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "PCRemoteControl", "target-password.bin");
    static byte[] Transform(byte[] bytes, bool protect)
    {
        var input = new Blob { size = bytes.Length, data = Marshal.AllocHGlobal(bytes.Length) };
        Blob output = default;
        try
        {
            Marshal.Copy(bytes, 0, input.data, bytes.Length);
            bool ok = protect ? CryptProtectData(ref input, null, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero, 1, out output)
                : CryptUnprotectData(ref input, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero, 1, out output);
            if (!ok) throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
            var result = new byte[output.size]; Marshal.Copy(output.data, result, 0, result.Length); return result;
        }
        finally { Marshal.FreeHGlobal(input.data); if (output.data != IntPtr.Zero) LocalFree(output.data); }
    }
    public static void Save(string password)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(FilePath)!);
        File.WriteAllBytes(FilePath + ".tmp", Transform(Encoding.UTF8.GetBytes(password), true));
        File.Move(FilePath + ".tmp", FilePath, true);
    }
    public static string? Load() => File.Exists(FilePath) ? Encoding.UTF8.GetString(Transform(File.ReadAllBytes(FilePath), false)) : null;
}
