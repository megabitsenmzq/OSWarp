using System;
using System.Drawing;
using System.Windows.Forms;

namespace OSWarp
{
    sealed class ListForm : Form
    {
        readonly Label info = new Label();
        readonly ListView list = new ListView();
        readonly FlowLayoutPanel buttons = new FlowLayoutPanel();
        readonly Button okButton = new Button();
        readonly Button cancelButton = new Button();

        int choice = -1;

        public static int Ask(
            string intro,
            string[] rows,
            string cancelText,
            Size size,
            Size minimum)
        {
            using (ListForm form = new ListForm(intro, rows, cancelText, size, minimum))
            {
                form.ShowDialog();
                return form.choice;
            }
        }

        ListForm(string intro, string[] rows, string cancelText, Size size, Size minimum)
        {
            Font = SystemFonts.MessageBoxFont;
            Text = "OSWarp";
            Icon extracted = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
            if (extracted != null)
                Icon = extracted;
            StartPosition = FormStartPosition.CenterScreen;
            ClientSize = size;
            MinimumSize = minimum;
            Padding = new Padding(16);

            info.AutoSize = true;
            info.Dock = DockStyle.Top;
            info.Padding = new Padding(0, 0, 0, 12);
            info.Text = intro;

            list.Dock = DockStyle.Fill;
            list.View = View.Details;
            list.FullRowSelect = true;
            list.MultiSelect = false;
            list.HideSelection = false;
            list.HeaderStyle = ColumnHeaderStyle.None;
            list.Columns.Add("Entry", size.Width - 40);
            foreach (string row in rows)
                list.Items.Add(new ListViewItem(row));
            list.SelectedIndexChanged += SelectionChanged;
            list.Resize += ListResized;

            buttons.AutoSize = true;
            buttons.WrapContents = false;
            buttons.FlowDirection = FlowDirection.RightToLeft;
            buttons.Dock = DockStyle.Bottom;
            buttons.Padding = new Padding(0, 12, 0, 0);
            okButton.Text = "OK";
            okButton.AutoSize = true;
            okButton.Enabled = false;
            okButton.Click += OkClicked;
            cancelButton.Text = cancelText;
            cancelButton.AutoSize = true;
            cancelButton.Click += delegate { Close(); };
            AcceptButton = okButton;
            CancelButton = cancelButton;

            Controls.Add(list);
            Controls.Add(info);
            Controls.Add(buttons);
            buttons.Controls.Add(cancelButton);
            buttons.Controls.Add(okButton);
        }

        void ListResized(object sender, EventArgs e)
        {
            int width = list.ClientSize.Width - 4;
            if (width >= 80)
                list.Columns[0].Width = width;
        }

        void SelectionChanged(object sender, EventArgs e)
        {
            okButton.Enabled = list.SelectedItems.Count == 1;
        }

        void OkClicked(object sender, EventArgs e)
        {
            if (list.SelectedItems.Count != 1)
                return;
            choice = list.SelectedItems[0].Index;
            DialogResult = DialogResult.OK;
            Close();
        }
    }
}
