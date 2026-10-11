using System;
using System.Drawing;
using System.Windows.Forms;

namespace OSWarp
{
    static class Program
    {
        public const string MethodLabel = "Boot method…";
        public const string EntryLabel = "Boot entry…";

        [STAThread]
        static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Run();
        }

        static void Run()
        {
            ConfigSettings settings = Config.Load();
            // Set boot method.
            if (settings.Boot.Length == 0)
            {
                string chosen = Prompt.AskBoot(IntPtr.Zero, settings.Boot);
                if (chosen == null)
                    return;
                try
                {
                    Config.Save(chosen, settings.SavedId);
                }
                catch (Exception ex)
                {
                    Prompt.Alert("The settings file could not be written.\n" + Config.ConfigPath() + "\n" + ex.Message);
                    return;
                }
                settings.Boot = chosen;
            }
            Boot.Mode = settings.Boot;

            // Set entries.
            string error = Boot.Load();
            if (error != null)
            {
                Prompt.Alert(error);
                return;
            }
            FirmwareEntry target = Config.Resolve(Boot.Entries, settings.SavedId, "Linux");
            if (target == null)
            {
                target = PickEntry(false);
                if (target == null)
                    return;
            }

            while (true)
            {
                int choice = Prompt.Ask(
                    "Reboot to " + target.Title + "?",
                    Effect());
                if (choice == Prompt.Config)
                {
                    int action = AskConfig();
                    if (action < 0)
                        continue; // Config canceled.
                    if (action == 0)
                    {
                        string chosen = Prompt.AskBoot(IntPtr.Zero, Boot.Mode);
                        if (chosen == null)
                            continue;
                        ChangeMode(chosen);
                        continue;
                    }
                    FirmwareEntry picked = PickEntry(true);
                    if (picked != null)
                        target = picked;
                    continue;
                }
                if (choice != Prompt.Reboot)
                    return;
                if (Boot.Mode == "bootorder" && Boot.Order.Count == 0)
                {
                    Prompt.Alert("Could not read the full boot order. Nothing was changed.");
                    continue;
                }
                string failure = Boot.Commit(target);
                if (failure == null)
                    return;
                Prompt.Alert(failure);
            }
        }

        public static int AskConfig()
        {
            return ListForm.Ask(
                "What do you want to change?",
                new string[] { MethodLabel, EntryLabel },
                "Cancel",
                new Size(480, 300),
                new Size(400, 240));
        }

        static FirmwareEntry PickEntry(bool canReturn)
        {
            string cancelText = canReturn ? "Back" : "Quit";
            while (true)
            {
                int picked = ListForm.Ask(
                    ListIntro(),
                    EntryRows(),
                    cancelText,
                    new Size(900, 780),
                    new Size(720, 560));
                if (picked < 0)
                    return null; // Canceled.
                if (RememberEntry(Boot.Entries[picked]))
                    return Boot.Entries[picked];
            }
        }

        static bool RememberEntry(FirmwareEntry entry)
        {
            try
            {
                Config.Save(Boot.Mode, entry.Id);
                return true;
            }
            catch (Exception ex)
            {
                Prompt.Alert(
                    "The settings file could not be written.\n" + Config.ConfigPath() + "\n" + ex.Message);
                return false;
            }
        }

        public static string Effect()
        {
            if (Boot.Mode == "bootnext")
                return "This will change only the next boot.";
            return "This will change the default boot order.";
        }

        static string ListIntro()
        {
            string hint = Boot.Mode == "bootnext" ? "Next boot only" : "Permanent boot order";
            return "Choose the correct boot entry. (" + hint + ")";
        }

        static string[] EntryRows()
        {
            string defaultId = Boot.Order.Count > 0 ? Boot.Order[0] : "";
            string[] rows = new string[Boot.Entries.Count];
            for (int i = 0; i < Boot.Entries.Count; i++)
                rows[i] = RowLabel(Boot.Entries[i], defaultId);
            return rows;
        }

        static string RowLabel(FirmwareEntry entry, string defaultId)
        {
            string title = entry.Title.Length > 0 ? entry.Title : entry.Id;
            if (!string.IsNullOrEmpty(defaultId)
                && string.Equals(entry.Id, defaultId, StringComparison.OrdinalIgnoreCase))
                title += " 〔DefaultBoot〕";
            return title + " · " + entry.Id;
        }

        static void ChangeMode(string mode)
        {
            try
            {
                Config.Save(mode, Config.Load().SavedId);
            }
            catch (Exception ex)
            {
                Prompt.Alert("The settings file could not be written.\n" + Config.ConfigPath() + "\n" + ex.Message);
                return;
            }
            Boot.Mode = mode;
        }
    }
}
