import subprocess

import pytest

from oswarp import actions


def make_completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


@pytest.fixture
def fake_efibootmgr(monkeypatch, efibootmgr_verbose, efibootmgr_plain):
    """Replace _efibootmgr with a recorder. Default responses come from the fixtures."""
    calls = []

    def fake(*args):
        calls.append(args)
        if args == ("-v",):
            return make_completed(stdout=efibootmgr_verbose)
        if args == ():
            return make_completed(stdout=efibootmgr_plain)
        return make_completed()

    monkeypatch.setattr(actions, "_efibootmgr", fake)
    return calls


class TestReadFirmware:
    def test_parses_fixture(self, fake_efibootmgr):
        view = actions.read_firmware()
        assert fake_efibootmgr == [("-v",)]
        assert view.order[0] == "0004"
        assert len(view.entries) == 6

    def test_failure_raises_action_error(self, monkeypatch):
        monkeypatch.setattr(
            actions, "_efibootmgr",
            lambda *args: make_completed(returncode=1, stderr="EFI variables are not supported on this system."),
        )
        with pytest.raises(actions.ActionError, match="not supported"):
            actions.read_firmware()

    def test_missing_tool_mentions_install_tip(self, monkeypatch):
        monkeypatch.setattr(actions.shutil, "which", lambda name: None)
        with pytest.raises(actions.ActionError, match="efibootmgr was not found"):
            actions.read_firmware()


class TestSetBootnext:
    def test_sets_known_entry(self, fake_efibootmgr):
        actions.set_bootnext("0005")
        assert fake_efibootmgr == [("-v",), ("-n", "0005")]

    def test_lowercase_id_is_normalized(self, monkeypatch):
        calls = []

        def fake(*args):
            calls.append(args)
            if args == ("-v",):
                return make_completed(stdout="BootOrder: 00AB\nBoot00AB* Fedora\t\\EFI\\fedora\\shimx64.efi\n")
            return make_completed()

        monkeypatch.setattr(actions, "_efibootmgr", fake)
        actions.set_bootnext("00ab")
        assert calls == [("-v",), ("-n", "00AB")]

    def test_invalid_id_rejected_without_calling_firmware(self, fake_efibootmgr):
        with pytest.raises(actions.ActionError, match="not valid"):
            actions.set_bootnext("xyz")
        assert fake_efibootmgr == []

    def test_unknown_id_rejected(self, fake_efibootmgr):
        with pytest.raises(actions.ActionError, match="not in the list"):
            actions.set_bootnext("0007")

    def test_efibootmgr_failure_raises(self, monkeypatch, efibootmgr_verbose):
        def fake(*args):
            if args == ("-v",):
                return make_completed(stdout=efibootmgr_verbose)
            return make_completed(returncode=2, stderr="Could not set BootNext: read-only variable")

        monkeypatch.setattr(actions, "_efibootmgr", fake)
        with pytest.raises(actions.ActionError, match="read-only variable"):
            actions.set_bootnext("0005")


class TestClearBootnext:
    def test_clears_when_bootnext_present(self, fake_efibootmgr):
        # The plain fixture was captured with BootNext set to 0004.
        actions.clear_bootnext()
        assert fake_efibootmgr == [(), ("-N",)]

    def test_noop_when_bootnext_absent(self, monkeypatch, efibootmgr_plain):
        without_next = "\n".join(
            line for line in efibootmgr_plain.splitlines()
            if not line.startswith("BootNext:")
        )
        calls = []

        def fake(*args):
            calls.append(args)
            return make_completed(stdout=without_next)

        monkeypatch.setattr(actions, "_efibootmgr", fake)
        actions.clear_bootnext()
        assert calls == [()]

    def test_read_failure_raises(self, monkeypatch):
        monkeypatch.setattr(actions, "_efibootmgr", lambda *args: make_completed(returncode=1, stderr="denied"))
        with pytest.raises(actions.ActionError, match="denied"):
            actions.clear_bootnext()


class TestSetBootOrder:
    def test_moves_entry_to_front_keeping_rest(self, fake_efibootmgr):
        actions.set_boot_order("0005")
        assert fake_efibootmgr == [("-v",), ("-o", "0005,0004,0001,0000,0003,0002")]

    def test_already_first(self, fake_efibootmgr):
        actions.set_boot_order("0004")
        assert fake_efibootmgr[-1] == ("-o", "0004,0005,0001,0000,0003,0002")

    def test_no_boot_order_line_rejects_every_entry(self, monkeypatch):
        # Without a BootOrder line no entries are listed, so nothing can be
        # selected and no write is attempted.
        calls = []

        def fake(*args):
            calls.append(args)
            return make_completed(stdout="Boot0001* Fedora\t\\EFI\\fedora\\shimx64.efi\n")

        monkeypatch.setattr(actions, "_efibootmgr", fake)
        with pytest.raises(actions.ActionError, match="not in the list"):
            actions.set_boot_order("0001")
        assert calls == [("-v",)]

    def test_write_failure_raises(self, monkeypatch, efibootmgr_verbose):
        def fake(*args):
            if args == ("-v",):
                return make_completed(stdout=efibootmgr_verbose)
            return make_completed(returncode=1, stderr="read-only variable")

        monkeypatch.setattr(actions, "_efibootmgr", fake)
        with pytest.raises(actions.ActionError, match="read-only variable"):
            actions.set_boot_order("0005")


class TestReboot:
    def fake_run(self, monkeypatch, results):
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            return results(command)

        monkeypatch.setattr(actions.subprocess, "run", run)
        return calls

    def which(self, monkeypatch, present):
        monkeypatch.setattr(
            actions.shutil, "which",
            lambda name: "/usr/bin/" + name if name in present else None,
        )

    def test_systemctl_success(self, monkeypatch):
        self.which(monkeypatch, {"systemctl", "shutdown"})
        calls = self.fake_run(monkeypatch, lambda command: make_completed())
        actions.reboot()
        assert calls == [["/usr/bin/systemctl", "reboot"]]

    def test_falls_back_to_shutdown(self, monkeypatch):
        self.which(monkeypatch, {"systemctl", "shutdown"})

        def results(command):
            if "systemctl" in command[0]:
                return make_completed(returncode=1, stderr="System is booting up")
            return make_completed()

        calls = self.fake_run(monkeypatch, results)
        actions.reboot()
        assert calls == [["/usr/bin/systemctl", "reboot"], ["/usr/bin/shutdown", "-r", "now"]]

    def test_all_fail_raises_last_error(self, monkeypatch):
        self.which(monkeypatch, {"systemctl", "shutdown"})
        self.fake_run(monkeypatch, lambda command: make_completed(returncode=1, stderr="nope"))
        with pytest.raises(actions.ActionError, match="nope"):
            actions.reboot()

    def test_no_reboot_tool(self, monkeypatch):
        self.which(monkeypatch, set())
        with pytest.raises(actions.ActionError, match="No tool for reboot"):
            actions.reboot()

    def test_oserror_from_subprocess(self, monkeypatch):
        self.which(monkeypatch, {"systemctl"})

        def run(command, **kwargs):
            raise OSError("missing executable")

        monkeypatch.setattr(actions.subprocess, "run", run)
        with pytest.raises(actions.ActionError, match="missing executable"):
            actions.reboot()


class TestRebootFirmwareSetup:
    def test_prefers_systemctl(self, monkeypatch, tmp_path):
        monkeypatch.setattr(actions.shutil, "which", lambda name: "/usr/bin/systemctl" if name == "systemctl" else None)
        calls = []
        monkeypatch.setattr(
            actions.subprocess, "run",
            lambda command, **kwargs: calls.append(command) or make_completed(),
        )
        actions.reboot_firmware_setup()
        assert calls == [["/usr/bin/systemctl", "reboot", "--firmware-setup"]]

    def test_missing_systemctl_raises(self, monkeypatch):
        monkeypatch.setattr(actions.shutil, "which", lambda name: None)
        with pytest.raises(actions.ActionError, match="systemctl was not found"):
            actions.reboot_firmware_setup()

    def test_systemctl_failure_propagates(self, monkeypatch):
        monkeypatch.setattr(actions.shutil, "which", lambda name: "/usr/bin/systemctl" if name == "systemctl" else None)
        monkeypatch.setattr(
            actions.subprocess, "run",
            lambda command, **kwargs: make_completed(returncode=1, stderr="not supported"),
        )
        with pytest.raises(actions.ActionError, match="not supported"):
            actions.reboot_firmware_setup()
