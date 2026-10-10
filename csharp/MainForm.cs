using System;
using System.Drawing;
using System.Windows.Forms;

namespace OSWarp
{
    sealed class MainForm : Form
    {
        readonly Label listInfo = new Label();
        readonly ListView list = new ListView();
        readonly Label listStatus = new Label();
        readonly TableLayoutPanel listButtons = new TableLayoutPanel();
        readonly FlowLayoutPanel actionButtons = new FlowLayoutPanel();
        readonly Button bootButton = new Button();
        readonly Button okButton = new Button();
        readonly Button backButton = new Button();

        readonly bool canReturn;
        bool goBack;
        bool busy;
        bool sized;

        public static bool ShowList(bool canReturn)
        {
            string error = Boot.Load();
            if (error != null)
            {
                Program.Alert(error);
                return false;
            }
            using (MainForm form = new MainForm(canReturn))
            {
                form.ShowDialog();
                return form.goBack;
            }
        }

        MainForm(bool canReturn)
        {
            this.canReturn = canReturn;
            Font = SystemFonts.MessageBoxFont;
            Text = "OSWarp";
            Icon extracted = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
            if (extracted != null)
                Icon = extracted;
            StartPosition = FormStartPosition.CenterScreen;
            MinimumSize = new Size(720, 560);
            Padding = new Padding(16);
            BuildList();
            Fill();
        }

        protected override void OnShown(EventArgs e)
        {
            base.OnShown(e);
            if (!sized)
            {
                sized = true;
                ClientSize = new Size(900, 780);
            }
            ResizeColumns();
        }

        protected override void OnFormClosing(FormClosingEventArgs e)
        {
            if (e.CloseReason == CloseReason.UserClosing && DialogResult != DialogResult.OK)
                goBack = canReturn;
            base.OnFormClosing(e);
        }

        void BuildList()
        {
            listInfo.AutoSize = true;
            listInfo.Dock = DockStyle.Top;
            listInfo.Padding = new Padding(0, 0, 0, 12);
            listInfo.Text = ListIntro();

            list.Dock = DockStyle.Fill;
            list.View = View.Details;
            list.FullRowSelect = true;
            list.MultiSelect = false;
            list.HideSelection = false;
            list.HeaderStyle = ColumnHeaderStyle.None;
            list.Columns.Add("Entry", 760);
            list.SelectedIndexChanged += ListSelectionChanged;
            list.Resize += ListResized;

            listStatus.AutoSize = true;
            listStatus.Dock = DockStyle.Bottom;
            listStatus.Padding = new Padding(0, 8, 0, 0);

            listButtons.Dock = DockStyle.Bottom;
            listButtons.AutoSize = true;
            listButtons.ColumnCount = 2;
            listButtons.RowCount = 1;
            listButtons.Padding = new Padding(0, 12, 0, 0);
            listButtons.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
            listButtons.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100F));

            bootButton.Text = "Boot method";
            bootButton.AutoSize = true;
            bootButton.Anchor = AnchorStyles.Left;
            bootButton.Click += ChangeBoot;

            actionButtons.AutoSize = true;
            actionButtons.WrapContents = false;
            actionButtons.FlowDirection = FlowDirection.RightToLeft;
            actionButtons.Anchor = AnchorStyles.Right;
            okButton.Text = "OK";
            okButton.AutoSize = true;
            okButton.Enabled = false;
            okButton.Click += ConfirmPick;
            backButton.Text = canReturn ? "Back" : "Quit";
            backButton.AutoSize = true;
            backButton.Click += BackFromList;
            CancelButton = backButton;

            Controls.Add(list);
            Controls.Add(listInfo);
            Controls.Add(listStatus);
            Controls.Add(listButtons);
            listButtons.Controls.Add(bootButton, 0, 0);
            listButtons.Controls.Add(actionButtons, 1, 0);
            actionButtons.Controls.Add(backButton);
            actionButtons.Controls.Add(okButton);
        }

        static string ListIntro()
        {
            string hint = Boot.Mode == "bootnext" ? "Next boot only" : "Permanent boot order";
            return "Choose the correct boot entry. (" + hint + ")";
        }

        void Fill()
        {
            list.BeginUpdate();
            list.Items.Clear();
            string defaultId = Boot.Order.Count > 0 ? Boot.Order[0] : "";
            foreach (FirmwareEntry entry in Boot.Entries)
            {
                ListViewItem item = new ListViewItem(RowLabel(entry, defaultId));
                item.Tag = entry;
                list.Items.Add(item);
            }
            list.EndUpdate();
            list.SelectedItems.Clear();
            UpdatePickButton();
        }

        void ListResized(object sender, EventArgs e)
        {
            ResizeColumns();
        }

        void ResizeColumns()
        {
            if (list.Columns.Count < 1)
                return;
            int width = list.ClientSize.Width - 4;
            if (width < 80)
                return;
            list.Columns[0].Width = width;
        }

        void ConfirmPick(object sender, EventArgs e)
        {
            if (busy || list.SelectedItems.Count != 1)
                return;
            if (Boot.Mode == "bootorder" && Boot.Order.Count == 0)
                return;
            FirmwareEntry entry = list.SelectedItems[0].Tag as FirmwareEntry;
            if (entry == null || !FirmwareList.ValidId(entry.Id))
                return;
            busy = true;
            okButton.Enabled = false;
            backButton.Enabled = false;
            bootButton.Enabled = false;
            listStatus.Text = "";
            string failure = Boot.Commit(entry);
            if (failure == null)
            {
                goBack = false;
                DialogResult = DialogResult.OK;
                Close();
                return;
            }
            busy = false;
            backButton.Enabled = true;
            bootButton.Enabled = true;
            UpdatePickButton();
            listStatus.Text = "";
            Program.Alert(failure);
        }

        void ChangeBoot(object sender, EventArgs e)
        {
            if (busy)
                return;
            string chosen = Prompt.AskBoot(Handle);
            if (chosen == null)
                return;
            TargetSettings settings = FirmwareList.LoadTarget();
            if (settings.Error.Length > 0)
            {
                Program.Alert(settings.Error);
                return;
            }
            try
            {
                FirmwareList.SaveTarget(chosen, settings.SavedId);
            }
            catch (Exception ex)
            {
                Program.Alert("The settings file could not be written.\n" + FirmwareList.TargetConfigPath() + "\n" + ex.Message);
                return;
            }
            Boot.Mode = chosen;
            listInfo.Text = ListIntro();
            UpdatePickButton();
        }

        void BackFromList(object sender, EventArgs e)
        {
            goBack = canReturn;
            Close();
        }

        void ListSelectionChanged(object sender, EventArgs e)
        {
            UpdatePickButton();
        }

        void UpdatePickButton()
        {
            bool orderReady = Boot.Mode != "bootorder" || Boot.Order.Count > 0;
            okButton.Enabled = list.SelectedItems.Count == 1 && orderReady && !busy;
            if (busy)
                return;
            listStatus.Text = Boot.Mode == "bootorder" && Boot.Order.Count == 0
                ? "Could not read the full boot order. Nothing was changed."
                : "";
        }

        static string RowLabel(FirmwareEntry entry, string defaultId)
        {
            string title = entry.Title.Length > 0 ? entry.Title : entry.Id;
            if (!string.IsNullOrEmpty(defaultId)
                && string.Equals(entry.Id, defaultId, StringComparison.OrdinalIgnoreCase))
                title += "    〔DefaultBoot〕";
            return title + "  ·  " + entry.Id;
        }
    }
}
