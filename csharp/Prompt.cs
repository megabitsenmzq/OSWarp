using System;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Windows.Forms;

namespace OSWarp
{
    static class Prompt
    {
        public const int Cancel = 2;
        public const int Reboot = 100;
        public const int Config = 101;
        public const int OrderChoice = 110;
        public const int NextChoice = 111;
        const int AllowCancel = 0x0008;
        const int UseMainIcon = 0x0002;

        public static int Ask(string instruction, string content)
        {
            TaskDialogButton[] buttons = new TaskDialogButton[3];
            buttons[0].Id = Reboot;
            buttons[0].Text = "Reboot";
            buttons[1].Id = Config;
            buttons[1].Text = "Config";
            buttons[2].Id = Cancel;
            buttons[2].Text = "Cancel";
            using (Icon icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath))
            {
                return AskWithIcon(instruction, content, icon, buttons, Reboot, IntPtr.Zero);
            }
        }

        public static string AskBoot(IntPtr owner, string current)
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
                    current == "bootnext" ? NextChoice : OrderChoice,
                    owner);
            }
            if (choice == OrderChoice)
                return "bootorder";
            if (choice == NextChoice)
                return "bootnext";
            return null;
        }

        public static void Alert(string text)
        {
            MessageBox.Show(text, "OSWarp", MessageBoxButtons.OK, MessageBoxIcon.None);
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
                    Alert("Could not open the confirmation window.\n" + hr.ToString("X8"));
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
