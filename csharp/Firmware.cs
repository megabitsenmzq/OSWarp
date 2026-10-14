using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Management;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;

namespace OSWarp
{
    public sealed class FirmwareEntry
    {
        public string Id = "";
        public string Title = "";
        public string Hint = "";
    }

    public sealed class FirmwareCatalog
    {
        public List<FirmwareEntry> Entries = new List<FirmwareEntry>();
        public List<string> Order = new List<string>();
        public bool HasOneShot;
        // False when displayorder held an id we could not read or recognize.
        public bool OrderComplete = true;
    }

    static class Firmware
    {
        internal const string ManagerId = "{a5a30fa2-3d06-4e9f-b5f4-a01df9d1fcba}";
        const uint DisplayOrderType = 0x24000001;
        const uint BootSequenceType = 0x24000002;
        const uint DescriptionType = 0x12000004;
        const uint ApplicationPathType = 0x12000002;

        static readonly Regex GuidId = new Regex(
            @"^\{[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\}$",
            RegexOptions.CultureInvariant);

        public static bool ValidId(string id)
        {
            if (string.Equals(id, "{bootmgr}", StringComparison.OrdinalIgnoreCase))
                return true;
            return id != null && GuidId.IsMatch(id);
        }

        // Reads the firmware through the BCD WMI provider.
        public static FirmwareCatalog Catalog()
        {
            ManagementScope scope = new ManagementScope("root\\WMI");
            scope.Options.Impersonation = ImpersonationLevel.Impersonate;
            scope.Options.EnablePrivileges = true;
            FirmwareCatalog catalog = new FirmwareCatalog();
            using (ManagementObject store = OpenAt(scope, "BcdStore.FilePath=\"\""))
                using (ManagementObject manager = OpenObject(scope, store, ManagerId))
                {
                    bool complete;
                    using (ManagementBaseObject displayOrder = Element(manager, DisplayOrderType))
                        catalog.Order = IdsOf(displayOrder, out complete);
                    catalog.OrderComplete = complete;
                    bool ignored;
                    using (ManagementBaseObject bootSequence = Element(manager, BootSequenceType))
                        catalog.HasOneShot = IdsOf(bootSequence, out ignored).Count > 0;
                    foreach (string id in catalog.Order)
                    {
                        // Keep an unreadable entry out of Entries, but leave its id
                        // in Order so rewriting the order does not drop it.
                        try
                        {
                            using (ManagementObject app = OpenObject(scope, store, id))
                            using (ManagementBaseObject description = Element(app, DescriptionType))
                            using (ManagementBaseObject path = Element(app, ApplicationPathType))
                                AddEntry(catalog, id, TextOf(description), TextOf(path));
                        }
                        catch (Exception)
                        {
                        }
                    }
                }
            return catalog;
        }

        static void AddEntry(FirmwareCatalog catalog, string id, string description, string path)
        {
            var entry = new FirmwareEntry();
            entry.Id = id;
            entry.Title = description.Length > 0 ? description : id;
            entry.Hint = Hint(entry.Title, path);
            catalog.Entries.Add(entry);
        }

        static ManagementObject OpenObject(ManagementScope scope, ManagementObject store, string id)
        {
            ManagementBaseObject input = store.GetMethodParameters("OpenObject");
            input["Id"] = id;
            using (ManagementBaseObject opened = store.InvokeMethod("OpenObject", input, null))
            {
                if (!BooleanResult(opened))
                    throw new IOException("The BCD WMI provider refused to open " + id + ".");
                return OpenAt(scope, "BcdObject.Id='" + id + "',StoreFilePath=''");
            }
        }

        static ManagementBaseObject Element(ManagementObject owner, uint type)
        {
            ManagementBaseObject input = owner.GetMethodParameters("GetElement");
            input["Type"] = type;
            try
            {
                using (ManagementBaseObject finished = owner.InvokeMethod("GetElement", input, null))
                {
                    if (!BooleanResult(finished))
                        return null;
                    return finished["Element"] as ManagementBaseObject;
                }
            }
            catch (ManagementException)
            {
                return null;
            }
            catch (COMException)
            {
                // A missing element comes back as a bare COM error.
                return null;
            }
        }

        static bool BooleanResult(ManagementBaseObject result)
        {
            if (result == null)
                return false;
            object code = result["ReturnValue"];
            if (code == null)
                return false;
            if (code is bool)
                return (bool)code;
            return Convert.ToUInt64(code) == 0;
        }

        // Method out-parameters come back as embedded objects without a path,
        // so bind the documented key of each class directly.
        static ManagementObject OpenAt(ManagementScope scope, string path)
        {
            ManagementObject located = new ManagementObject(scope, new ManagementPath(path), null);
            located.Get();
            return located;
        }

        static List<string> IdsOf(ManagementBaseObject element, out bool complete)
        {
            complete = true;
            var ids = new List<string>();
            if (element == null)
                return ids;
            object value = null;
            try
            {
                value = element["Ids"];
            }
            catch (ManagementException)
            {
                complete = false;
                return ids;
            }
            catch (COMException)
            {
                complete = false;
                return ids;
            }
            if (value == null || value is string)
                return ids;
            IEnumerable enumerable = value as IEnumerable;
            if (enumerable == null)
            {
                complete = false;
                return ids;
            }
            foreach (object item in enumerable)
            {
                string id = item as string;
                if (!string.IsNullOrEmpty(id) && ValidId(id))
                    ids.Add(id);
                else
                    complete = false;
            }
            return ids;
        }

        static string TextOf(ManagementBaseObject element)
        {
            if (element == null)
                return "";
            try
            {
                return (element["String"] as string) ?? "";
            }
            catch (ManagementException)
            {
                return "";
            }
            catch (COMException)
            {
                return "";
            }
        }

        public static string[] OrderWith(IList<string> order, string selected)
        {
            if (!ValidId(selected))
                throw new InvalidDataException("The boot entry id is not valid.");
            if (order == null || order.Count == 0)
                throw new InvalidDataException("Could not read the full boot order. Nothing was changed.");
            var next = new List<string>();
            next.Add(selected);
            foreach (string raw in order)
            {
                if (!ValidId(raw))
                    throw new InvalidDataException("The boot order contains an unrecognized entry. Nothing was changed.");
                bool seen = false;
                foreach (string have in next)
                {
                    if (string.Equals(have, raw, StringComparison.OrdinalIgnoreCase))
                        seen = true;
                }
                if (!seen)
                    next.Add(raw);
            }
            return next.ToArray();
        }

        public static string Hint(string title, string path)
        {
            string found = Classify(path);
            if (found.Length > 0)
                return found;
            return Classify(title);
        }

        // Windows is \EFI\Microsoft\ or bootmgfw.efi.
        // Linux is shim*.efi, grub*.efi, or systemd-boot*.efi.
        // The shared \EFI\BOOT\BOOTX64.EFI fallback is neither.
        static string Classify(string text)
        {
            if (string.IsNullOrEmpty(text))
                return "";
            string folded = text.Replace('/', '\\').ToLowerInvariant();
            if (folded.Contains("\\efi\\microsoft\\") || folded.StartsWith("efi\\microsoft\\"))
                return "Windows";
            string file = LoaderFile(folded);
            if (file.Equals("bootmgfw.efi"))
                return "Windows";
            if (!file.EndsWith(".efi"))
                return "";
            if (file.StartsWith("shim") || file.StartsWith("grub") || file.StartsWith("systemd-boot"))
                return "Linux";
            return "";
        }

        static string LoaderFile(string folded)
        {
            int slash = folded.LastIndexOf('\\');
            string file = slash >= 0 ? folded.Substring(slash + 1) : folded;
            int space = file.IndexOf(' ');
            if (space >= 0)
                file = file.Substring(0, space);
            return file;
        }

        // bcdedit error output on a pipe may be wide text, UTF-8, or the ANSI
        // code page. Pick the decoding with the fewest damaged characters.
        public static string DecodeOutput(byte[] data)
        {
            return DecodeOutput(data, Encoding.Default);
        }

        // The ANSI code page is a parameter so tests can replay byte dumps
        // captured on machines with another system locale.
        internal static string DecodeOutput(byte[] data, Encoding ansi)
        {
            if (data == null || data.Length == 0)
                return "";
            if (IsUtf16Le(data))
                return Encoding.Unicode.GetString(data).TrimStart('\uFEFF');
            string candidate = ansi.GetString(data);
            try
            {
                string utf8 = new UTF8Encoding(false, true).GetString(data);
                if (ReplacementCount(utf8) < ReplacementCount(candidate))
                    candidate = utf8;
            }
            catch (ArgumentException)
            {
            }
            return candidate;
        }

        static int ReplacementCount(string text)
        {
            int count = 0;
            for (int i = 0; i < text.Length; i++)
            {
                if (text[i] == '\uFFFD')
                    count++;
            }
            return count;
        }

        static bool IsUtf16Le(byte[] data)
        {
            if (data.Length >= 2 && data[0] == 0xFF && data[1] == 0xFE)
                return true;
            if (data.Length < 8 || (data.Length % 2) != 0)
                return false;
            int pairs = data.Length / 2;
            int asciiNull = 0;
            for (int i = 0; i + 1 < data.Length; i += 2)
            {
                if (data[i + 1] == 0 && data[i] >= 0x20 && data[i] < 0x7F)
                    asciiNull++;
            }
            return asciiNull >= 4 && asciiNull * 5 >= pairs;
        }

        const string GlobalVariable = "{8be4df61-93ca-11d2-aa0d-00e098032b8c}";

        // Ask the firmware to open its setup UI at the next boot
        // (EFI_OS_INDICATIONS_BOOT_TO_FW_UI), keeping every other bit.
        public static void RequestFirmwareSetup()
        {
            EnableEnvironmentPrivilege();
            var buffer = new byte[8];
            if (GetFirmwareEnvironmentVariableEx("OsIndicationsSupported", GlobalVariable, buffer, 8, IntPtr.Zero) < 8)
                throw new IOException("Could not read the firmware boot indications. Error " + Marshal.GetLastWin32Error() + ".");
            ulong supported = BitConverter.ToUInt64(buffer, 0);
            if ((supported & 1) == 0)
                throw new IOException("The firmware does not support opening its setup on request.");
            ulong current = 0;
            if (GetFirmwareEnvironmentVariableEx("OsIndications", GlobalVariable, buffer, 8, IntPtr.Zero) >= 8)
                current = BitConverter.ToUInt64(buffer, 0);
            byte[] payload = BitConverter.GetBytes(current | 1);
            // Attributes: non-volatile + boot service access + runtime access.
            if (!SetFirmwareEnvironmentVariableEx("OsIndications", GlobalVariable, payload, (uint)payload.Length, 7))
                throw new IOException("Could not request the firmware setup. Error " + Marshal.GetLastWin32Error() + ".");
        }

        // Firmware environment variables need SeSystemEnvironmentPrivilege,
        // which an admin token holds but keeps disabled by default.
        static void EnableEnvironmentPrivilege()
        {
            using (Process current = Process.GetCurrentProcess())
            {
                IntPtr token;
                if (!OpenProcessToken(current.Handle, 0x0020, out token)) // TOKEN_ADJUST_PRIVILEGES
                    throw new IOException("Could not open the process token. Error " + Marshal.GetLastWin32Error() + ".");
                try
                {
                    var privileges = new TokenPrivileges();
                    privileges.Count = 1;
                    privileges.Attributes = 0x00000002; // SE_PRIVILEGE_ENABLED
                    if (!LookupPrivilegeValue(null, "SeSystemEnvironmentPrivilege", out privileges.Luid))
                        throw new IOException("Could not find the privilege. Error " + Marshal.GetLastWin32Error() + ".");
                    if (!AdjustTokenPrivileges(token, false, ref privileges, 0, IntPtr.Zero, IntPtr.Zero)
                        || Marshal.GetLastWin32Error() != 0)
                        throw new IOException("Could not enable the privilege. Error " + Marshal.GetLastWin32Error() + ".");
                }
                finally
                {
                    CloseHandle(token);
                }
            }
        }

        [StructLayout(LayoutKind.Sequential)]
        struct Luid
        {
            public uint LowPart;
            public int HighPart;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct TokenPrivileges
        {
            public int Count;
            public Luid Luid;
            public int Attributes;
        }

        [DllImport("advapi32.dll", SetLastError = true)]
        static extern bool OpenProcessToken(IntPtr process, uint access, out IntPtr token);

        [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        static extern bool LookupPrivilegeValue(string system, string name, out Luid luid);

        [DllImport("advapi32.dll", SetLastError = true)]
        static extern bool AdjustTokenPrivileges(
            IntPtr token, bool disableAll, ref TokenPrivileges next, int size, IntPtr previous, IntPtr adjusted);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool CloseHandle(IntPtr handle);

        [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        static extern uint GetFirmwareEnvironmentVariableEx(
            string name, string guid, byte[] buffer, uint size, IntPtr attributes);

        [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        static extern bool SetFirmwareEnvironmentVariableEx(
            string name, string guid, byte[] value, uint size, uint attributes);
    }
}
