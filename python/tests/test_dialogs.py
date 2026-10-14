from oswarp.dialogs import _ask_confirm_argv


class TestAskConfirmArgv:
    def test_kdialog(self):
        argv = _ask_confirm_argv("/usr/bin/kdialog", "Reboot into the firmware setup?")
        assert "--yesno" in argv
        assert argv[argv.index("--yes-label") + 1] == "Reboot"
        assert argv[argv.index("--no-label") + 1] == "Cancel"
        assert argv[-1] == "Reboot into the firmware setup?"

    def test_yad(self):
        argv = _ask_confirm_argv("yad", "Reboot into the firmware setup?")
        assert "Reboot:0" in argv
        assert "Cancel:1" in argv

    def test_zenity(self):
        argv = _ask_confirm_argv("/usr/bin/zenity", "Reboot into the firmware setup?")
        assert "--question" in argv
        assert argv[argv.index("--ok-label") + 1] == "Reboot"
        assert argv[argv.index("--cancel-label") + 1] == "Cancel"
