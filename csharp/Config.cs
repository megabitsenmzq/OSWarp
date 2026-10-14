using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace OSWarp
{
    public sealed class ConfigSettings
    {
        public string Boot = "";
        public string SavedId = "";
    }

    static class Config
    {
        public static FirmwareEntry Resolve(IList<FirmwareEntry> entries, string savedId, string hint)
        { // Use the saved id when it is still listed. Otherwise rematch.
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

        public static string ConfigPath()
        {
            return Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
                "OSWarp",
                "config.txt");
        }

        public static ConfigSettings Load()
        {
            return Load(ConfigPath());
        }

        // A missing, unreadable, or corrupted file is treated as no settings;
        public static ConfigSettings Load(string path)
        {
            try
            {
                return Read(path);
            }
            catch (Exception)
            {
                return new ConfigSettings();
            }
        }

        static ConfigSettings Read(string path)
        {
            var result = new ConfigSettings();
            string text = File.ReadAllText(path);
            text = text.Replace("\r\n", "\n").Replace("\r", "\n");
            if (text.EndsWith("\n")) // Blank line at end.
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
            bool sawBoot = false;
            bool sawId = false;
            foreach (string line in lines)
            {
                int split = line.IndexOf('=');
                if (split < 1)
                    return new ConfigSettings();
                string key = line.Substring(0, split);
                string value = line.Substring(split + 1);
                if (key == "boot")
                {
                    value = value.ToLowerInvariant();
                    if (sawBoot || (value != "bootorder" && value != "bootnext"))
                        return new ConfigSettings();
                    sawBoot = true;
                    result.Boot = value;
                }
                else if (key == "id")
                {
                    if (sawId || !Firmware.ValidId(value))
                        return new ConfigSettings();
                    sawId = true;
                    result.SavedId = value;
                }
                else
                {
                    return new ConfigSettings();
                }
            }
            return result;
        }

        public static void Save(string boot, string savedId)
        {
            Save(ConfigPath(), boot, savedId);
        }

        internal static void Save(string path, string boot, string savedId)
        {
            if (boot != "bootorder" && boot != "bootnext")
                throw new InvalidDataException("The boot setting is not valid.");
            var text = new StringBuilder();
            text.Append("boot=");
            text.Append(boot);
            text.Append("\r\n");
            if (!string.IsNullOrEmpty(savedId))
            {
                if (!Firmware.ValidId(savedId))
                    throw new InvalidDataException("The boot entry id is not valid.");
                text.Append("id=");
                text.Append(savedId);
                text.Append("\r\n");
            }
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            string tmp = path + ".tmp";
            try
            {
                File.WriteAllText(tmp, text.ToString());
                if (File.Exists(path))
                    File.Replace(tmp, path, null);
                else
                    File.Move(tmp, path);
            }
            catch (Exception)
            {
                try
                {
                    File.Delete(tmp);
                }
                catch (Exception)
                {
                }
                throw;
            }
        }

    }
}
