import subprocess
from pathlib import Path

import pytest

from oswarp import elevate


class TestExplainRoot:
    def test_cancelled(self):
        assert elevate._explain_root("", 126) == "Authorization was cancelled. Boot entries were not changed."

    def test_cancelled_beats_other_output(self):
        assert "cancelled" in elevate._explain_root("some noise", 126)

    def test_no_authentication_agent(self):
        text = elevate._explain_root("Error: No authentication agent available.", 1)
        assert text.startswith("No authentication agent was found.")
        assert "No authentication agent available." in text

    def test_not_authorized(self):
        text = elevate._explain_root("pkexec: not authorized", 1)
        assert text.startswith("Authorization did not finish.")

    def test_authentication_failed(self):
        text = elevate._explain_root("authentication failed for user", 1)
        assert text.startswith("Authorization did not finish.")

    def test_other_output_passes_through(self):
        assert elevate._explain_root("efibootmgr: permission denied\n", 1) == "efibootmgr: permission denied"

    def test_empty_output(self):
        assert elevate._explain_root("", 1) == ""


class TestElevateCommand:
    def test_builds_pkexec_command(self):
        command = elevate.elevate_command(Path("/usr/local/bin/oswarp"), ["0005", "bootnext"], pkexec="/usr/bin/pkexec")
        assert command == ["/usr/bin/pkexec", "/usr/local/bin/oswarp", "0005", "bootnext"]


class TestPkexecBin:
    def test_missing_pkexec_exits(self, monkeypatch):
        monkeypatch.setattr(elevate.shutil, "which", lambda name: None)
        with pytest.raises(SystemExit):
            elevate.pkexec_bin()

    def test_found(self, monkeypatch):
        monkeypatch.setattr(elevate.shutil, "which", lambda name: "/usr/bin/pkexec")
        assert elevate.pkexec_bin() == "/usr/bin/pkexec"


class TestEnsureExecutable:
    def test_makes_file_executable(self, tmp_path):
        helper = tmp_path / "helper.sh"
        helper.write_text("#!/bin/sh\n")
        helper.chmod(0o644)
        elevate.ensure_executable(helper)
        assert helper.stat().st_mode & 0o111


class TestFirmwareSetup:
    def test_commit_reboots_into_setup(self, monkeypatch):
        calls = []
        monkeypatch.setattr(elevate, "reboot_firmware_setup", lambda: calls.append("ok"))
        assert elevate.commit(None, elevate.FIRMWARE_SETUP) == 0
        assert calls == ["ok"]

    def test_commit_reports_failure(self, monkeypatch):
        def fail():
            raise elevate.ActionError("no firmware setup")

        monkeypatch.setattr(elevate, "reboot_firmware_setup", fail)
        assert elevate.commit(None, elevate.FIRMWARE_SETUP) == 1

    def test_as_root_does_not_save_a_choice(self, monkeypatch):
        monkeypatch.setattr(elevate.os, "geteuid", lambda: 1000)
        monkeypatch.setattr(elevate, "_elevate_commit", lambda boot_id, boot: (0, ""))

        def boom(boot_id, boot):
            raise AssertionError("must not save a choice")

        monkeypatch.setattr(elevate, "_save_choice", boom)
        assert elevate.as_root(None, elevate.FIRMWARE_SETUP) == (0, "")

    def test_elevate_command_omits_the_id(self, monkeypatch, tmp_path):
        # Not root: as_root must go through pkexec (a root CI run would
        # otherwise take _run_commit and reboot for real).
        monkeypatch.setattr(elevate.os, "geteuid", lambda: 1000)
        helper = tmp_path / "run.sh"
        helper.write_text("#!/bin/sh\n")
        monkeypatch.setattr(elevate, "helper_path", lambda: helper)
        monkeypatch.setattr(elevate, "pkexec_bin", lambda: "/usr/bin/pkexec")
        seen = {}

        def fake_run(command, **kwargs):
            seen["command"] = command
            return subprocess.CompletedProcess(command, 0, "", "")

        monkeypatch.setattr(elevate.subprocess, "run", fake_run)
        assert elevate.as_root(None, elevate.FIRMWARE_SETUP) == (0, "")
        assert seen["command"] == ["/usr/bin/pkexec", str(helper), "firmwaresetup"]


def test_save_choice_requires_a_boot_id():
    with pytest.raises(ValueError, match="boot_id is required"):
        elevate._save_choice(None, "bootnext")
