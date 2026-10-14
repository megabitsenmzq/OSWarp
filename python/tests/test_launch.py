from oswarp import launch


def _as_pkexec_root(monkeypatch):
    monkeypatch.setattr(launch.os, "geteuid", lambda: 0)
    monkeypatch.setenv("PKEXEC_UID", "1000")


class TestPkexecBoot:
    def test_accepts_boot_methods(self, monkeypatch):
        _as_pkexec_root(monkeypatch)
        assert launch._pkexec_boot(["0004", "bootnext"]) == ("0004", "bootnext")
        assert launch._pkexec_boot(["0004", "bootorder"]) == ("0004", "bootorder")

    def test_accepts_firmware_setup_without_id(self, monkeypatch):
        _as_pkexec_root(monkeypatch)
        assert launch._pkexec_boot(["firmwaresetup"]) == (None, "firmwaresetup")

    def test_rejects_firmware_setup_with_id(self, monkeypatch):
        _as_pkexec_root(monkeypatch)
        assert launch._pkexec_boot(["0000", "firmwaresetup"]) is None

    def test_rejects_unknown_mode(self, monkeypatch):
        _as_pkexec_root(monkeypatch)
        assert launch._pkexec_boot(["0004", "bogus"]) is None

    def test_rejects_non_root(self, monkeypatch):
        monkeypatch.setattr(launch.os, "geteuid", lambda: 1000)
        monkeypatch.setenv("PKEXEC_UID", "1000")
        assert launch._pkexec_boot(["0004", "bootnext"]) is None

    def test_rejects_without_pkexec_marker(self, monkeypatch):
        monkeypatch.setattr(launch.os, "geteuid", lambda: 0)
        monkeypatch.delenv("PKEXEC_UID", raising=False)
        assert launch._pkexec_boot(["0004", "bootnext"]) is None
