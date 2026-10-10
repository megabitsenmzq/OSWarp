using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading.Tasks;
using System.Drawing;
using System.Windows.Forms;

namespace OSWarp
{
    static class Program
    {
        [STAThread]
        static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Run();
        }

        static void Run()
        {
            TargetSettings settings = FirmwareList.LoadTarget();
            if (settings.Error.Length > 0)
            {
                Alert(settings.Error);
                return;
            }
            if (settings.Boot.Length == 0)
            {
                string chosen = Prompt.AskBoot(IntPtr.Zero);
                if (chosen == null)
                    return;
                try
                {
                    FirmwareList.SaveTarget(chosen, settings.SavedId);
                }
                catch (Exception ex)
                {
                    Alert("The settings file could not be written.\n" + FirmwareList.TargetConfigPath() + "\n" + ex.Message);
                    return;
                }
                settings.Boot = chosen;
            }
            Boot.Mode = settings.Boot;
            string error = Boot.Load();
            if (error != null)
            {
                Alert(error);
                return;
            }
            FirmwareEntry target = FirmwareList.Resolve(Boot.Entries, settings.SavedId, "Linux");
            if (target == null)
            {
                MainForm.ShowList(false);
                return;
            }
            while (true)
            {
                int choice = Prompt.Ask(
                    "Reboot to " + target.Title + "?",
                    Boot.Effect());
                if (choice == Prompt.Pick)
                {
                    if (!MainForm.ShowList(true))
                        return;
                    error = Boot.Load();
                    if (error != null)
                    {
                        Alert(error);
                        return;
                    }
                    FirmwareEntry again = FirmwareList.Resolve(
                        Boot.Entries, settings.SavedId, "Linux");
                    if (again == null)
                    {
                        MainForm.ShowList(false);
                        return;
                    }
                    target = again;
                    continue;
                }
                if (choice != Prompt.Reboot)
                    return;
                if (Boot.Mode == "bootorder" && Boot.Order.Count == 0)
                {
                    Alert("Could not read the full boot order. Nothing was changed.");
                    continue;
                }
                string failure = Boot.Commit(target);
                if (failure == null)
                    return;
                Alert(failure);
            }
        }

        public static void Alert(string text)
        {
            MessageBox.Show(text, "OSWarp", MessageBoxButtons.OK, MessageBoxIcon.None);
        }
    }

    static class Boot
    {
        public static string Mode = "";
        public static bool HasOneShot;
        public static List<FirmwareEntry> Entries = new List<FirmwareEntry>();
        public static List<string> Order = new List<string>();

        public static string Effect()
        {
            if (Mode == "bootnext")
                return "This will change only the next boot.";
            return "This will change the default boot order.";
        }

        public static string Load()
        {
            Entries = new List<FirmwareEntry>();
            Order = new List<string>();
            HasOneShot = false;
            try
            {
                string text = RunBcdedit("/enum firmware");
                Entries = FirmwareList.Parse(text);
                try
                {
                    Order = FirmwareList.ParseDisplayOrder(text);
                    HasOneShot = FirmwareList.OneShotIsSet(text);
                }
                catch (InvalidDataException)
                {
                }
                if (Entries.Count == 0)
                    return EmptyEntries(text);
                return null;
            }
            catch (Exception ex)
            {
                return "Could not read firmware boot entries.\n" + ex.Message;
            }
        }

        public static string Commit(FirmwareEntry entry)
        {
            if (Mode != "bootorder" && Mode != "bootnext")
                return "The boot setting is not valid.";
            byte[] backup;
            string remembered = RememberChoice(entry, out backup);
            if (remembered != null)
                return remembered;
            string failure = Mode == "bootnext" ? CommitNext(entry) : CommitOrder(entry);
            if (failure != null)
                FirmwareList.RestoreTarget(backup);
            return failure;
        }

        static string CommitOrder(FirmwareEntry entry)
        {
            try
            {
                string[] next = FirmwareList.OrderWith(Order, entry.Id);
                RunBcdedit("/set {fwbootmgr} displayorder " + string.Join(" ", next));
            }
            catch (Exception ex)
            {
                return "Did not reboot.\n" + ex.Message;
            }
            if (HasOneShot)
            {
                try
                {
                    RunBcdedit("/deletevalue {fwbootmgr} bootsequence");
                }
                catch (Exception ex)
                {
                    return "The boot order was changed, but the next-boot setting could not be cleared.\n" + ex.Message;
                }
            }
            try
            {
                Reboot();
                return null;
            }
            catch (Exception ex)
            {
                return "The boot order was changed, but the reboot did not happen.\n" + ex.Message;
            }
        }

        static string CommitNext(FirmwareEntry entry)
        {
            try
            {
                RunBcdedit("/set {fwbootmgr} bootsequence " + entry.Id);
            }
            catch (Exception ex)
            {
                return "Did not reboot.\n" + ex.Message;
            }
            try
            {
                Reboot();
                return null;
            }
            catch (Exception ex)
            {
                return "The next boot was changed, but the reboot did not happen.\n" + ex.Message;
            }
        }

        // Save the chosen entry, keeping a backup so a failed commit can be rolled back.
        static string RememberChoice(FirmwareEntry entry, out byte[] backup)
        {
            try
            {
                backup = FirmwareList.BackupTarget();
            }
            catch (Exception ex)
            {
                backup = null;
                return "Did not reboot.\nThe settings file could not be read.\n" + FirmwareList.TargetConfigPath() + "\n" + ex.Message;
            }
            try
            {
                FirmwareList.SaveTarget(Mode, entry.Id);
            }
            catch (Exception)
            {
            }
            return null;
        }

        static string RunBcdedit(string arguments)
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
                string stdout = FirmwareList.DecodeOutput(raw.GetBytes(stdoutRaw));
                string stderr = FirmwareList.DecodeOutput(raw.GetBytes(stderrRaw));
                if (process.ExitCode != 0)
                {
                    string detail = (stderr + "\r\n" + stdout).Trim();
                    throw new IOException(detail.Length > 0 ? detail : "bcdedit failed. The boot order was not changed.");
                }
                return stdout;
            }
        }

        static string EmptyEntries(string text)
        {
            string trimmed = (text ?? "").Trim();
            if (trimmed.Length == 0)
                return "No firmware boot entries. bcdedit produced no output.";
            if (trimmed.Length > 180)
                trimmed = trimmed.Substring(0, 180);
            return "Could not parse boot entries.\n" + trimmed;
        }

        static void Reboot()
        {
            ProcessStartInfo start = new ProcessStartInfo();
            start.FileName = Path.Combine(Environment.SystemDirectory, "shutdown.exe");
            start.Arguments = "/r /t 0";
            start.UseShellExecute = false;
            Process.Start(start);
        }
    }

    static class Prompt
    {
        public const int Cancel = 2;
        public const int Reboot = 100;
        public const int Pick = 101;
        public const int OrderChoice = 110;
        public const int NextChoice = 111;
        const int AllowCancel = 0x0008;
        const int UseMainIcon = 0x0002;

        public static int Ask(string instruction, string content)
        {
            TaskDialogButton[] buttons = new TaskDialogButton[3];
            buttons[0].Id = Reboot;
            buttons[0].Text = "Reboot";
            buttons[1].Id = Pick;
            buttons[1].Text = "Choose entry";
            buttons[2].Id = Cancel;
            buttons[2].Text = "Cancel";
            using (Icon icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath))
            {
                return AskWithIcon(instruction, content, icon, buttons, Reboot, IntPtr.Zero);
            }
        }

        public static string AskBoot(IntPtr owner)
        {
            TaskDialogButton[] buttons = new TaskDialogButton[3];
            buttons[0].Id = OrderChoice;
            buttons[0].Text = "Permanent boot order";
            buttons[1].Id = NextChoice;
            buttons[1].Text = "Next boot only";
            buttons[2].Id = Cancel;
            buttons[2].Text = "Cancel";
            int choice;
            using (Icon icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath))
            {
                choice = AskWithIcon(
                    "Change the permanent boot order, or only the next boot?",
                    null,
                    icon,
                    buttons,
                    OrderChoice,
                    owner);
            }
            if (choice == OrderChoice)
                return "bootorder";
            if (choice == NextChoice)
                return "bootnext";
            return null;
        }

        static int AskWithIcon(
            string instruction,
            string content,
            Icon icon,
            TaskDialogButton[] buttons,
            int defaultButton,
            IntPtr owner)
        {
            int size = Marshal.SizeOf(typeof(TaskDialogButton));
            IntPtr buffer = Marshal.AllocHGlobal(size * buttons.Length);
            int written = 0;
            try
            {
                for (; written < buttons.Length; written++)
                    Marshal.StructureToPtr(buttons[written], IntPtr.Add(buffer, written * size), false);

                TaskDialogConfig config = new TaskDialogConfig();
                config.cbSize = (uint)Marshal.SizeOf(typeof(TaskDialogConfig));
                config.dwFlags = AllowCancel;
                if (icon != null)
                {
                    config.dwFlags |= UseMainIcon;
                    config.hMainIcon = icon.Handle;
                }
                config.pszWindowTitle = "OSWarp";
                config.pszMainInstruction = instruction;
                config.pszContent = content;
                config.cButtons = (uint)buttons.Length;
                config.pButtons = buffer;
                config.hwndParent = owner;
                config.nDefaultButton = defaultButton;

                int button;
                int radio;
                int verification;
                int hr = TaskDialogIndirect(ref config, out button, out radio, out verification);
                if (hr != 0)
                {
                    Program.Alert("Could not open the confirmation window.\n" + hr.ToString("X8"));
                    return Cancel;
                }
                return button;
            }
            finally
            {
                for (int i = 0; i < written; i++)
                    Marshal.DestroyStructure(IntPtr.Add(buffer, i * size), typeof(TaskDialogButton));
                Marshal.FreeHGlobal(buffer);
            }
        }

        [DllImport("comctl32.dll", CharSet = CharSet.Unicode, ExactSpelling = true)]
        static extern int TaskDialogIndirect(
            ref TaskDialogConfig config,
            out int button,
            out int radioButton,
            out int verificationFlagChecked);

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode, Pack = 1)]
        struct TaskDialogButton
        {
            public int Id;
            public string Text;
        }

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode, Pack = 1)]
        struct TaskDialogConfig
        {
            public uint cbSize;
            public IntPtr hwndParent;
            public IntPtr hInstance;
            public int dwFlags;
            public int dwCommonButtons;
            public string pszWindowTitle;
            public IntPtr hMainIcon;
            public string pszMainInstruction;
            public string pszContent;
            public uint cButtons;
            public IntPtr pButtons;
            public int nDefaultButton;
            public uint cRadioButtons;
            public IntPtr pRadioButtons;
            public int nDefaultRadioButton;
            public string pszVerificationText;
            public string pszExpandedInformation;
            public string pszExpandedControlText;
            public string pszCollapsedControlText;
            public IntPtr hFooterIcon;
            public string pszFooter;
            public IntPtr pfCallback;
            public IntPtr lpCallbackData;
            public uint cxWidth;
        }
    }
}
