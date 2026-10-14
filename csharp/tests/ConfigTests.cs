using System;
using System.IO;

namespace OSWarp.Tests
{
    // Config read/write against a temporary directory, never the real file.
    static class ConfigTests
    {
        const string G1 = "{9dea862c-5cdd-4e70-acc1-f32b344d4795}";

        public static void Run()
        {
            string dir = Path.Combine(Path.GetTempPath(), "oswarp-tests-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(dir);
            try
            {
                LoadCorrupt(dir);
                Roundtrip(dir);
            }
            finally
            {
                Directory.Delete(dir, true);
            }
        }

        static string Write(string dir, string name, string content)
        {
            string path = Path.Combine(dir, name);
            File.WriteAllText(path, content);
            return path;
        }

        static void LoadCorrupt(string dir)
        {
            T.Eq("Config: missing file is empty", "", Config.Load(Path.Combine(dir, "nope.txt")).Boot);

            ConfigSettings ok = Config.Load(Write(dir, "ok.txt", "boot=bootnext\r\nid=" + G1 + "\r\n"));
            T.Eq("Config: reads boot", "bootnext", ok.Boot);
            T.Eq("Config: reads id", G1, ok.SavedId);

            T.Eq("Config: boot lowercased", "bootorder", Config.Load(Write(dir, "upper.txt", "boot=BootOrder\n")).Boot);
            T.Eq("Config: lf endings", "bootnext", Config.Load(Write(dir, "lf.txt", "boot=bootnext\n")).Boot);

            string[] corrupt =
            {
                "boot=bogus\r\n",                          // unknown boot value
                "boot=bootnext\r\nboot=bootorder\r\n",     // duplicate key
                "boot=bootnext\r\nother=x\r\n",            // unknown key
                "boot=bootnext\r\nid=not-a-guid\r\n",      // invalid id
                "no separator here\r\n",                   // line without '='
                "boot\r\n",                                // bare key
            };
            for (int i = 0; i < corrupt.Length; i++)
            {
                ConfigSettings settings = Config.Load(Write(dir, "bad" + i + ".txt", corrupt[i]));
                T.Check("Config: corrupt file " + i + " falls back to empty",
                    settings.Boot.Length == 0 && settings.SavedId.Length == 0);
            }
        }

        static void Roundtrip(string dir)
        {
            string path = Path.Combine(dir, "saved", "config.txt");
            Config.Save(path, "bootnext", G1);
            ConfigSettings loaded = Config.Load(path);
            T.Eq("Config: roundtrip boot", "bootnext", loaded.Boot);
            T.Eq("Config: roundtrip id", G1, loaded.SavedId);
            T.Check("Config: no tmp file left", !File.Exists(path + ".tmp"));

            string noId = Path.Combine(dir, "noid.txt");
            Config.Save(noId, "bootorder", "");
            T.Eq("Config: save without id", "boot=bootorder\r\n", File.ReadAllText(noId));

            Config.Save(path, "bootorder", G1.ToUpperInvariant());
            T.Eq("Config: overwrite existing", "bootorder", Config.Load(path).Boot);

            T.Throws<InvalidDataException>("Config: invalid boot rejected",
                delegate { Config.Save(Path.Combine(dir, "x1.txt"), "bogus", G1); });
            T.Throws<InvalidDataException>("Config: invalid id rejected",
                delegate { Config.Save(Path.Combine(dir, "x2.txt"), "bootnext", "junk"); });
        }
    }
}
