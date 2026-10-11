using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading.Tasks;

namespace OSWarp
{
    static class Actions
    {
        public static void RunBcdedit(string arguments)
        {
            ProcessStartInfo start = new ProcessStartInfo();
            start.FileName = Path.Combine(Environment.SystemDirectory, "bcdedit.exe");
            start.Arguments = arguments;
            start.UseShellExecute = false;
            start.RedirectStandardOutput = true;
            start.RedirectStandardError = true;
            start.CreateNoWindow = true;
            // Code page 28591 keeps the raw bytes. DecodeOutput then picks UTF-16, UTF-8, or the system code page.
            Encoding raw = Encoding.GetEncoding(28591);
            start.StandardOutputEncoding = raw;
            start.StandardErrorEncoding = raw;
            using (Process process = Process.Start(start))
            {
                // Read both pipes at once so a full stderr buffer cannot block the process.
                Task<string> stdoutTask = Task.Run(() => process.StandardOutput.ReadToEnd());
                string stderrRaw = process.StandardError.ReadToEnd();
                string stdoutRaw = stdoutTask.Result;
                process.WaitForExit();
                string stdout = Firmware.DecodeOutput(raw.GetBytes(stdoutRaw));
                string stderr = Firmware.DecodeOutput(raw.GetBytes(stderrRaw));
                if (process.ExitCode != 0)
                {
                    string detail = (stderr + "\r\n" + stdout).Trim();
                    throw new IOException(detail.Length > 0 ? detail : "bcdedit failed. The boot order was not changed.");
                }
            }
        }

        public static void Reboot()
        {
            ProcessStartInfo start = new ProcessStartInfo();
            start.FileName = Path.Combine(Environment.SystemDirectory, "shutdown.exe");
            start.Arguments = "/r /t 0";
            start.UseShellExecute = false;
            Process.Start(start);
        }
    }
}
