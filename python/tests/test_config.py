import pytest

from oswarp.config import Config, load_config, resolve_target, save_config
from oswarp.firmware import FirmwareEntry


def make_entry(boot_id, hint=""):
    return FirmwareEntry(boot_id=boot_id, title="entry " + boot_id, path="", active=True, hint=hint)


class TestLoadConfig:
    def test_missing_file(self, tmp_path):
        assert load_config(tmp_path / "nope" / "config") == Config(boot="", saved_id="")

    def test_valid_full(self, tmp_path):
        path = tmp_path / "config"
        path.write_text("boot=bootnext\nid=0005\n", encoding="utf-8")
        assert load_config(path) == Config(boot="bootnext", saved_id="0005")

    def test_valid_without_id(self, tmp_path):
        path = tmp_path / "config"
        path.write_text("boot=bootorder\n", encoding="utf-8")
        assert load_config(path) == Config(boot="bootorder", saved_id="")

    def test_boot_value_is_lowercased(self, tmp_path):
        path = tmp_path / "config"
        path.write_text("boot=BootOrder\n", encoding="utf-8")
        assert load_config(path).boot == "bootorder"

    def test_id_is_uppercased(self, tmp_path):
        path = tmp_path / "config"
        path.write_text("boot=bootnext\nid=00ab\n", encoding="utf-8")
        assert load_config(path).saved_id == "00AB"

    def test_crlf_and_blank_lines(self, tmp_path):
        path = tmp_path / "config"
        path.write_bytes(b"boot=bootnext\r\n\r\nid=0005\r\n")
        assert load_config(path) == Config(boot="bootnext", saved_id="0005")

    @pytest.mark.parametrize("text", [
        "boot=bogus\n",                    # unknown boot value
        "boot=bootnext\nboot=bootorder\n", # duplicate key
        "boot=bootnext\nother=x\n",        # unknown key
        "boot=bootnext\nid=ZZZZ\n",        # invalid id
        "boot=bootnext\nid=005\n",         # short id
        "no separator here\n",             # line without '='
        "boot\n",                          # bare key
        "id=0005\nid=0006\n",              # duplicate id
    ])
    def test_corrupt_files_fall_back_to_empty(self, tmp_path, text):
        path = tmp_path / "config"
        path.write_text(text, encoding="utf-8")
        assert load_config(path) == Config(boot="", saved_id="")

    def test_invalid_utf8(self, tmp_path):
        path = tmp_path / "config"
        path.write_bytes(b"boot=bootnext\nid=00\xff\n")
        assert load_config(path) == Config(boot="", saved_id="")

    def test_empty_file(self, tmp_path):
        path = tmp_path / "config"
        path.write_text("\n\n", encoding="utf-8")
        assert load_config(path) == Config(boot="", saved_id="")


class TestSaveConfig:
    def test_roundtrip(self, tmp_path):
        path = tmp_path / "oswarp" / "config"
        save_config(path, "bootnext", "0005")
        assert load_config(path) == Config(boot="bootnext", saved_id="0005")

    def test_roundtrip_without_id(self, tmp_path):
        path = tmp_path / "config"
        save_config(path, "bootorder", "")
        assert path.read_text(encoding="utf-8") == "boot=bootorder\n"
        assert load_config(path) == Config(boot="bootorder", saved_id="")

    def test_creates_parent_directories(self, tmp_path):
        path = tmp_path / "deep" / "nested" / "config"
        save_config(path, "bootorder", "0001")
        assert path.is_file()

    def test_file_permissions(self, tmp_path):
        path = tmp_path / "config"
        save_config(path, "bootnext", "0005")
        assert (path.stat().st_mode & 0o777) == 0o600

    def test_overwrites_existing(self, tmp_path):
        path = tmp_path / "config"
        save_config(path, "bootnext", "0005")
        save_config(path, "bootorder", "0004")
        assert load_config(path) == Config(boot="bootorder", saved_id="0004")

    def test_no_tmp_file_left_behind(self, tmp_path):
        path = tmp_path / "config"
        save_config(path, "bootnext", "0005")
        assert not (tmp_path / "config.tmp").exists()

    def test_invalid_boot_raises(self, tmp_path):
        with pytest.raises(ValueError):
            save_config(tmp_path / "config", "bogus", "0005")

    def test_invalid_id_raises(self, tmp_path):
        with pytest.raises(ValueError):
            save_config(tmp_path / "config", "bootnext", "not-an-id")


class TestResolveTarget:
    entries = (
        make_entry("0004", hint="Windows"),
        make_entry("0005", hint="Linux"),
        make_entry("0002"),
    )

    def test_saved_id_still_listed(self):
        assert resolve_target(self.entries, "0005", "Windows").boot_id == "0005"

    def test_saved_id_wins_over_hint(self):
        # Saved id points at the Windows entry even though hint says Linux.
        assert resolve_target(self.entries, "0004", "Linux").boot_id == "0004"

    def test_saved_id_gone_falls_back_to_hint(self):
        assert resolve_target(self.entries, "9999", "Linux").boot_id == "0005"

    def test_no_saved_id_uses_hint(self):
        assert resolve_target(self.entries, "", "Windows").boot_id == "0004"

    def test_multiple_hint_matches_give_up(self):
        entries = self.entries + (make_entry("0006", hint="Linux"),)
        assert resolve_target(entries, "9999", "Linux") is None

    def test_no_match(self):
        assert resolve_target(self.entries, "", "Linux") is not None
        assert resolve_target(self.entries, "9999", "macOS") is None
