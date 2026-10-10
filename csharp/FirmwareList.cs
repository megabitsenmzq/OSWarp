using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;

namespace OSWarp
{
    public sealed class TargetSettings
    {
        public string Boot = "";
        public string SavedId = "";
        public string Error = "";
    }

    public sealed class FirmwareEntry
    {
        public string Id = "";
        public string Title = "";
        public string Path = "";
        public string Hint = "";
    }

    static class FirmwareList
    {
        static readonly Regex GuidId = new Regex(
            @"^\{[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\}$",
            RegexOptions.CultureInvariant);

        public static bool ValidId(string id)
        {
            if (string.Equals(id, "{bootmgr}", StringComparison.OrdinalIgnoreCase))
                return true;
            return id != null && GuidId.IsMatch(id);
        }

        public static List<FirmwareEntry> Parse(string text)
        {
            var entries = new List<FirmwareEntry>();
            string section = "";
            string id = "";
            string description = "";
            string path = "";
            string[] lines = (text ?? "").Replace("\r\n", "\n").Split('\n');
            foreach (string raw in lines)
            {
                string line = raw.TrimEnd();
                string trimmed = line.Trim();
                if (trimmed.Length == 0)
                {
                    Flush(entries, section, id, description, path);
                    section = "";
                    id = "";
                    description = "";
                    path = "";
                    continue;
                }
                if (trimmed.Trim('-').Length == 0)
                    continue;
                int split = KeySplit(line);
                if (split < 0)
                {
                    if (id.Length > 0 || description.Length > 0 || path.Length > 0)
                    {
                        Flush(entries, section, id, description, path);
                        id = "";
                        description = "";
                        path = "";
                    }
                    section = trimmed;
                    continue;
                }
                string value = line.Substring(split).Trim();
                // The key name is localized. Use the shape of the value instead.
                if (id.Length == 0 && IsRecordId(value))
                    id = value;
                else if (path.Length == 0 && IsEfiPath(value))
                    path = value;
                else if (description.Length == 0 && IsDescription(value))
                    description = value;
            }
            Flush(entries, section, id, description, path);
            return entries;
        }

        static void Flush(List<FirmwareEntry> entries, string section, string id, string description, string path)
        {
            if (id.Length == 0)
                return;
            if (string.Equals(id, "{fwbootmgr}", StringComparison.OrdinalIgnoreCase))
                return;
            if (!ValidId(id))
                return;
            var entry = new FirmwareEntry();
            entry.Id = id;
            entry.Title = description.Length > 0 ? description : section;
            entry.Path = path;
            entry.Hint = Hint(entry.Title, path);
            if (entry.Title.Length == 0)
                return;
            entries.Add(entry);
        }

        static bool IsRecordId(string value)
        {
            if (string.Equals(value, "{fwbootmgr}", StringComparison.OrdinalIgnoreCase))
                return true;
            return ValidId(value);
        }

        static bool IsEfiPath(string value)
        {
            if (value.Length < 5 || value[0] != '\\')
                return false;
            if (value.IndexOf(".efi", StringComparison.OrdinalIgnoreCase) >= 0)
                return true;
            return value.IndexOf("\\EFI\\", StringComparison.OrdinalIgnoreCase) >= 0;
        }

        static bool IsDescription(string value)
        {
            if (value.Length == 0 || IsBraceToken(value) || IsEfiPath(value))
                return false;
            if (IsDevice(value) || IsLocale(value) || IsInteger(value))
                return false;
            return true;
        }

        static bool IsDevice(string value)
        {
            if (value.IndexOf('=') >= 0)
                return true;
            return value.IndexOf("\\Device\\", StringComparison.OrdinalIgnoreCase) >= 0;
        }

        static bool IsLocale(string value)
        {
            int dash = value.IndexOf('-');
            if (dash < 2 || dash > 3 || dash >= value.Length - 1)
                return false;
            for (int i = 0; i < value.Length; i++)
            {
                char c = value[i];
                if (c == '-')
                    continue;
                if (!char.IsLetterOrDigit(c))
                    return false;
            }
            return true;
        }

        static bool IsInteger(string value)
        {
            int number;
            return int.TryParse(value, out number);
        }

        static bool IsBraceToken(string value)
        {
            return value.Length >= 2 && value[0] == '{' && value[value.Length - 1] == '}';
        }

        static int KeySplit(string line)
        {
            for (int i = 0; i < line.Length; i++)
            {
                if (line[i] == '\t')
                    return i;
                if (char.IsWhiteSpace(line[i]))
                {
                    int j = i + 1;
                    while (j < line.Length && line[j] != '\t' && char.IsWhiteSpace(line[j]))
                        j++;
                    if (j - i >= 2)
                        return i;
                    i = j - 1;
                }
            }
            return -1;
        }

        public static string DecodeOutput(byte[] data)
        {
            if (data == null || data.Length == 0)
                return "";
            if (IsUtf16Le(data))
                return Encoding.Unicode.GetString(data).TrimStart('\uFEFF');
            int oem = 0;
            try
            {
                oem = System.Globalization.CultureInfo.CurrentCulture.TextInfo.OEMCodePage;
            }
            catch (ArgumentException)
            {
                oem = 0;
            }
            string best = "";
            int bestCount = -1;
            Consider(ref best, ref bestCount, Decode(data, oem));
            Consider(ref best, ref bestCount, Encoding.UTF8.GetString(data));
            try
            {
                Consider(ref best, ref bestCount, Encoding.Default.GetString(data));
            }
            catch (ArgumentException)
            {
            }
            if (bestCount <= 0 && data.Length % 2 == 0)
            {
                string wide = Encoding.Unicode.GetString(data).TrimStart('\uFEFF');
                if (Parse(wide).Count > 0)
                    return wide;
            }
            return best;
        }

        static void Consider(ref string best, ref int bestCount, string text)
        {
            if (text == null)
                text = "";
            text = text.TrimStart('\uFEFF');
            int count = Parse(text).Count;
            if (count > bestCount)
            {
                best = text;
                bestCount = count;
                return;
            }
            if (count == bestCount && count > 0 && ReplacementCount(text) < ReplacementCount(best))
            {
                best = text;
                bestCount = count;
            }
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

        static string Decode(byte[] data, int codePage)
        {
            if (codePage <= 0)
                return "";
            try
            {
                return Encoding.GetEncoding(codePage).GetString(data);
            }
            catch (ArgumentException)
            {
                return "";
            }
            catch (NotSupportedException)
            {
                return "";
            }
        }

        static bool IsUtf16Le(byte[] data)
        {
            if (data.Length >= 2 && data[0] == 0xFF && data[1] == 0xFE)
                return true;
            if (data.Length < 32 || (data.Length % 2) != 0)
                return false;
            int asciiNull = 0;
            int pairs = data.Length / 2;
            for (int i = 0; i + 1 < data.Length; i += 2)
            {
                if (data[i + 1] == 0 && data[i] >= 0x20 && data[i] < 0x7F)
                    asciiNull++;
            }
            return asciiNull >= 12 && asciiNull * 5 >= pairs;
        }

        public static List<string> ParseDisplayOrder(string text)
        {
            var order = new List<string>();
            string ignored;
            ReadManager(text, order, out ignored);
            return order;
        }

        // The firmware manager block is the one whose first id is {fwbootmgr}.
        // A keyed line starts a new id list. An indented line continues the current list.
        // The first list is the permanent order. The next list's first id is the one-shot boot.
        // Key names are ignored. Only the shape of each value is used.
        static void ReadManager(string text, List<string> order, out string bootSequence)
        {
            bootSequence = "";
            bool inManager = false;
            bool sawIdentity = false;
            bool listOpen = false;
            int listIndex = -1;
            string[] lines = (text ?? "").Replace("\r\n", "\n").Split('\n');
            foreach (string raw in lines)
            {
                string line = raw.TrimEnd();
                string trimmed = line.Trim();
                if (trimmed.Length == 0)
                {
                    if (inManager)
                        return;
                    sawIdentity = false;
                    listOpen = false;
                    continue;
                }
                if (trimmed.Trim('-').Length == 0)
                    continue;
                int split = KeySplit(line);
                if (split < 0)
                {
                    if (!inManager)
                        continue;
                    if (ValidId(trimmed))
                    {
                        TakeListId(order, ref bootSequence, ref listOpen, ref listIndex, trimmed);
                        continue;
                    }
                    if (listOpen && IsBraceToken(trimmed))
                        throw new InvalidDataException("The boot order contains an unrecognized entry. Nothing was changed.");
                    listOpen = false;
                    continue;
                }
                string value = line.Substring(split).Trim();
                bool keyed = line.Substring(0, split).Trim().Length > 0;
                if (!sawIdentity && IsRecordId(value))
                {
                    sawIdentity = true;
                    inManager = string.Equals(value, "{fwbootmgr}", StringComparison.OrdinalIgnoreCase);
                    continue;
                }
                if (!inManager)
                    continue;
                if (ValidId(value))
                {
                    // A new field ends the previous list, so the one-shot boot is not merged into the order.
                    if (keyed && listOpen)
                        listOpen = false;
                    TakeListId(order, ref bootSequence, ref listOpen, ref listIndex, value);
                    continue;
                }
                // An indented unknown id is inside the order. A new field, such as a setting, just ends the list.
                if (!keyed && listOpen && IsBraceToken(value))
                    throw new InvalidDataException("The boot order contains an unrecognized entry. Nothing was changed.");
                listOpen = false;
            }
        }

        static void TakeListId(
            List<string> order,
            ref string bootSequence,
            ref bool listOpen,
            ref int listIndex,
            string value)
        {
            if (!listOpen)
            {
                listIndex++;
                listOpen = true;
            }
            if (listIndex == 0)
                AddOrder(order, value);
            else if (listIndex == 1 && bootSequence.Length == 0)
                bootSequence = value;
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

        static void AddOrder(List<string> order, string value)
        {
            if (!ValidId(value))
                throw new InvalidDataException("The boot order contains an unrecognized entry. Nothing was changed.");
            foreach (string have in order)
            {
                if (string.Equals(have, value, StringComparison.OrdinalIgnoreCase))
                    return;
            }
            order.Add(value);
        }

        public static FirmwareEntry Resolve(IList<FirmwareEntry> entries, string savedId, string hint)
        {
            if (!string.IsNullOrEmpty(savedId))
            {
                foreach (FirmwareEntry entry in entries)
                {
                    if (string.Equals(entry.Id, savedId, StringComparison.OrdinalIgnoreCase))
                        return entry;
                }
            }
            FirmwareEntry found = null;
            int count = 0;
            foreach (FirmwareEntry entry in entries)
            {
                if (entry.Hint == hint)
                {
                    found = entry;
                    count++;
                }
            }
            if (count == 1)
                return found;
            return null;
        }

        public static string TargetConfigPath()
        {
            return Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
                "OSWarp",
                "target.txt");
        }

        public static bool OneShotIsSet(string text)
        {
            var order = new List<string>();
            string sequence;
            ReadManager(text, order, out sequence);
            return sequence.Length > 0;
        }

        public static TargetSettings LoadTarget()
        {
            return LoadTarget(TargetConfigPath());
        }

        public static TargetSettings LoadTarget(string path)
        {
            var result = new TargetSettings();
            string text;
            try
            {
                text = File.ReadAllText(path);
            }
            catch (DirectoryNotFoundException)
            {
                // The OSWarp directory is created by SaveTarget. A missing directory
                // is not a FileNotFoundException, and it is not a broken file.
                return result;
            }
            catch (FileNotFoundException)
            {
                return result;
            }
            catch (IOException ex)
            {
                result.Error = SettingsError(path, ex.Message);
                return result;
            }
            catch (UnauthorizedAccessException ex)
            {
                result.Error = SettingsError(path, ex.Message);
                return result;
            }
            text = text.Replace("\r\n", "\n").Replace("\r", "\n");
            if (text.EndsWith("\n"))
                text = text.Substring(0, text.Length - 1);
            var lines = new List<string>();
            foreach (string raw in text.Split('\n'))
            {
                string line = raw.Trim();
                if (line.Length == 0)
                    continue;
                lines.Add(line);
            }
            if (lines.Count == 0)
                return result;
            if (lines.Count == 1 && lines[0].IndexOf('=') < 0)
            {
                if (ValidId(lines[0]))
                {
                    result.SavedId = lines[0];
                    return result;
                }
                result.Error = SettingsError(path, "");
                return result;
            }
            bool sawBoot = false;
            bool sawId = false;
            foreach (string line in lines)
            {
                int split = line.IndexOf('=');
                if (split < 1)
                {
                    result.Error = SettingsError(path, "");
                    return result;
                }
                string key = line.Substring(0, split);
                string value = line.Substring(split + 1);
                if (key == "boot")
                {
                    value = value.ToLowerInvariant();
                    if (sawBoot || (value != "bootorder" && value != "bootnext"))
                    {
                        result.Error = SettingsError(path, "");
                        return result;
                    }
                    sawBoot = true;
                    result.Boot = value;
                }
                else if (key == "id")
                {
                    if (sawId || !ValidId(value))
                    {
                        result.Error = SettingsError(path, "");
                        return result;
                    }
                    sawId = true;
                    result.SavedId = value;
                }
                else
                {
                    result.Error = SettingsError(path, "");
                    return result;
                }
            }
            return result;
        }

        public static void SaveTarget(string boot, string savedId)
        {
            if (boot != "bootorder" && boot != "bootnext")
                throw new InvalidDataException("The boot setting is not valid.");
            var text = new StringBuilder();
            text.Append("boot=");
            text.Append(boot);
            text.Append("\r\n");
            if (!string.IsNullOrEmpty(savedId))
            {
                if (!ValidId(savedId))
                    throw new InvalidDataException("The boot entry id is not valid.");
                text.Append("id=");
                text.Append(savedId);
                text.Append("\r\n");
            }
            string path = TargetConfigPath();
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            File.WriteAllText(path, text.ToString());
        }

        public static byte[] BackupTarget()
        {
            return BackupTarget(TargetConfigPath());
        }

        // A null backup means the file did not exist; restoring it deletes the file again.
        public static byte[] BackupTarget(string path)
        {
            try
            {
                return File.ReadAllBytes(path);
            }
            catch (FileNotFoundException)
            {
                return null;
            }
            catch (DirectoryNotFoundException)
            {
                return null;
            }
        }

        public static void RestoreTarget(byte[] backup)
        {
            RestoreTarget(TargetConfigPath(), backup);
        }

        public static void RestoreTarget(string path, byte[] backup)
        {
            try
            {
                if (backup == null)
                {
                    File.Delete(path);
                }
                else
                {
                    Directory.CreateDirectory(Path.GetDirectoryName(path));
                    File.WriteAllBytes(path, backup);
                }
            }
            catch (Exception)
            {
            }
        }

        static string SettingsError(string path, string detail)
        {
            string text = "The settings file could not be read.\n" + path + "\nUse boot=bootorder or boot=bootnext.";
            if (!string.IsNullOrEmpty(detail))
                text += "\n" + detail;
            return text;
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
    }
}
