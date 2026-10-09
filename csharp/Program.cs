using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
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
            string error = Boot.Load();
            if (error != null)
            {
                Alert(error);
                return;
            }
            FirmwareEntry target = FirmwareList.Resolve(Boot.Entries, FirmwareList.LoadSavedId(), "Linux");
            if (target == null)
            {
                MainForm.ShowList(false);
                return;
            }
            while (true)
            {
                int choice = Prompt.Ask(
                    "Reboot to " + target.Title + "?",
                    "This will change the default boot order.");
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
                        Boot.Entries, FirmwareList.LoadSavedId(), "Linux");
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
                if (Boot.Order.Count == 0)
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
        public static List<FirmwareEntry> Entries = new List<FirmwareEntry>();
        public static List<string> Order = new List<string>();

        public static string Load()
        {
            Entries = new List<FirmwareEntry>();
            Order = new List<string>();
            try
            {
                string text = RunBcdedit("/enum firmware");
                Entries = FirmwareList.Parse(text);
                try
                {
                    Order = FirmwareList.ParseDisplayOrder(text);
                }
                catch (InvalidDataException)
                {
                    Order = new List<string>();
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
            try
            {
                string[] next = FirmwareList.OrderWith(Order, entry.Id);
                RunBcdedit("/set {fwbootmgr} displayorder " + string.Join(" ", next));
            }
            catch (Exception ex)
            {
                return "Did not reboot.\n" + ex.Message;
            }
            try
            {
                FirmwareList.SaveId(entry.Id);
            }
            catch (Exception)
            {
            }
            try
            {
                RunBcdedit("/set {fwbootmgr} bootsequence " + entry.Id);
                Reboot();
                return null;
            }
            catch (Exception ex)
            {
                return "The boot order was changed, but the reboot did not happen.\n" + ex.Message;
            }
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
                string stdoutRaw = process.StandardOutput.ReadToEnd();
                string stderrRaw = process.StandardError.ReadToEnd();
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
        const int AllowCancel = 0x0008;
        const int UseMainIcon = 0x0002;

        public static int Ask(string instruction, string content)
        {
            using (Icon icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath))
            {
                return AskWithIcon(instruction, content, icon);
            }
        }

        static int AskWithIcon(string instruction, string content, Icon icon)
        {
            TaskDialogButton[] buttons = new TaskDialogButton[3];
            buttons[0].Id = Reboot;
            buttons[0].Text = "Reboot";
            buttons[1].Id = Pick;
            buttons[1].Text = "Choose entry";
            buttons[2].Id = Cancel;
            buttons[2].Text = "Cancel";

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
                config.nDefaultButton = Reboot;

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
