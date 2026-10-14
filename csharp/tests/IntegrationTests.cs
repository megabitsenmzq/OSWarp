using System;
using System.Diagnostics;
using System.IO;
using System.Security.Principal;
using System.Text;

namespace OSWarp.Tests
{
    // Tests that touch the real machine: the BCD WMI provider, a live
    // bcdedit run, and replaying captured bcdedit byte dumps.
    //
    // Dumps live in a test-data directory next to the exe and are named
    // after the ANSI code page of the machine that produced them, e.g.
    // bcdedit-cp936.bin. The live run stores one automatically when this
    // machine's code page has no dump yet.
    static class IntegrationTests
    {
        const string DumpPrefix = "bcdedit-cp";

        public static void Run()
        {
            DecodeCapturedDumps();
            CaptureLiveOutput();
            CatalogSmoke();
        }

        static string DumpDir()
        {
            return Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "test-data");
        }

        static void DecodeCapturedDumps()
        {
            string dir = DumpDir();
            if (!Directory.Exists(dir))
            {
                T.Skip("DecodeOutput: captured dumps", "no test-data directory next to the exe");
                return;
            }
            string[] files = Directory.GetFiles(dir, DumpPrefix + "*.bin");
            if (files.Length == 0)
            {
                T.Skip("DecodeOutput: captured dumps", "no dumps yet; the live run stores one");
                return;
            }
            foreach (string file in files)
            {
                string name = Path.GetFileNameWithoutExtension(file);
                int codePage;
                if (!int.TryParse(name.Substring(DumpPrefix.Length), out codePage))
                {
                    T.Skip("DecodeOutput: " + Path.GetFileName(file), "unrecognized dump name");
                    continue;
                }
                string text = Firmware.DecodeOutput(File.ReadAllBytes(file), Encoding.GetEncoding(codePage));
                T.Check("DecodeOutput: " + Path.GetFileName(file),
                    text.Length > 0 && text.IndexOf('\uFFFD') < 0);
            }
        }

        static void CaptureLiveOutput()
        {
            if (!IsAdmin())
            {
                T.Skip("live bcdedit output", "needs administrator");
                return;
            }
            int exitCode;
            byte[] raw = RunBcdeditRaw("/enum firmware", out exitCode);
            if (exitCode != 0)
            {
                Console.WriteLine("      bcdedit exited with code " + exitCode);
                T.Check("live bcdedit runs", false);
                return;
            }
            T.Check("live bcdedit runs", true);
            string text = Firmware.DecodeOutput(raw);
            T.Check("live bcdedit decodes cleanly",
                text.Length > 0 && text.IndexOf('\uFFFD') < 0);

            string file = Path.Combine(DumpDir(), DumpPrefix + Encoding.Default.CodePage + ".bin");
            if (!File.Exists(file))
            {
                Directory.CreateDirectory(DumpDir());
                File.WriteAllBytes(file, raw);
                Console.WriteLine("      saved dump for this code page: " + Path.GetFileName(file));
            }
        }

        // Same raw-byte pipe setup as Actions.RunBcdedit, but keeps the output.
        static byte[] RunBcdeditRaw(string arguments, out int exitCode)
        {
            ProcessStartInfo start = new ProcessStartInfo();
            start.FileName = Path.Combine(Environment.SystemDirectory, "bcdedit.exe");
            start.Arguments = arguments;
            start.UseShellExecute = false;
            start.RedirectStandardOutput = true;
            start.RedirectStandardError = true;
            start.CreateNoWindow = true;
            Encoding raw = Encoding.GetEncoding(28591);
            start.StandardOutputEncoding = raw;
            start.StandardErrorEncoding = raw;
            using (Process process = Process.Start(start))
            {
                string stdout = process.StandardOutput.ReadToEnd();
                process.StandardError.ReadToEnd();
                process.WaitForExit();
                exitCode = process.ExitCode;
                return raw.GetBytes(stdout);
            }
        }

        static bool IsAdmin()
        {
            WindowsIdentity identity = WindowsIdentity.GetCurrent();
            return new WindowsPrincipal(identity).IsInRole(WindowsBuiltInRole.Administrator);
        }

        static void CatalogSmoke()
        {
            if (!IsAdmin())
            {
                T.Skip("Catalog smoke", "run this exe as administrator to test the WMI provider");
                return;
            }
            FirmwareCatalog catalog;
            try
            {
                catalog = Firmware.Catalog();
            }
            catch (Exception ex)
            {
                Console.WriteLine("      " + ex.GetType().Name + ": " + ex.Message);
                T.Check("Catalog: reads firmware", false);
                return;
            }
            T.Check("Catalog: reads firmware", true);
            T.Check("Catalog: order not empty", catalog.Order.Count > 0);

            bool idsValid = true;
            foreach (string id in catalog.Order)
            {
                if (!Firmware.ValidId(id))
                {
                    Console.WriteLine("      invalid id in order: " + id);
                    idsValid = false;
                }
            }
            T.Check("Catalog: order ids valid", idsValid);
            T.Check("Catalog: entries not empty", catalog.Entries.Count > 0);

            bool entriesInOrder = true;
            foreach (FirmwareEntry entry in catalog.Entries)
            {
                bool found = false;
                foreach (string id in catalog.Order)
                {
                    if (string.Equals(id, entry.Id, StringComparison.OrdinalIgnoreCase))
                        found = true;
                }
                if (!found)
                {
                    Console.WriteLine("      entry not in order: " + entry.Id);
                    entriesInOrder = false;
                }
            }
            T.Check("Catalog: entries belong to order", entriesInOrder);

            if (catalog.OrderComplete)
            {
                // Putting the current default first must reproduce the order.
                string[] same = Firmware.OrderWith(catalog.Order, catalog.Order[0]);
                T.Eq("Catalog: OrderWith is a no-op on the real order",
                    string.Join(" ", catalog.Order.ToArray()),
                    string.Join(" ", same));
            }

            Console.WriteLine("      firmware entries on this machine:");
            foreach (FirmwareEntry entry in catalog.Entries)
                Console.WriteLine("      " + entry.Id + "  " + entry.Title + "  [" + entry.Hint + "]");
            Console.WriteLine("      one-shot bootsequence set: " + catalog.HasOneShot);
        }
    }
}
