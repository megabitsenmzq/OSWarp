import pytest

from oswarp.firmware import (
    boot_order_with,
    check_boot_id,
    firmware_marks,
    parse_efibootmgr,
    _classify,
    _hint,
)

EXPECTED_ORDER = ("0004", "0005", "0001", "0000", "0003", "0002")


class TestParseEfibootmgr:
    def test_order_and_entries_follow_boot_order(self, efibootmgr_verbose):
        view = parse_efibootmgr(efibootmgr_verbose)
        assert view.order == EXPECTED_ORDER
        assert [entry.boot_id for entry in view.entries] == list(EXPECTED_ORDER)

    def test_titles_and_paths(self, efibootmgr_verbose):
        view = parse_efibootmgr(efibootmgr_verbose)
        by_id = {entry.boot_id: entry for entry in view.entries}
        assert by_id["0004"].title == "Windows Boot Manager"
        assert by_id["0004"].path.startswith("HD(1,GPT,9ab9531a-2517-4999-9153-97b4a9634314")
        assert "\\EFI\\Microsoft\\Boot\\bootmgfw.efi" in by_id["0004"].path
        assert by_id["0005"].title == "Fedora"
        assert by_id["0005"].path.endswith("\\EFI\\fedora\\shimaa64.efi")
        assert by_id["0002"].title == "EFI Network"

    def test_all_entries_active(self, efibootmgr_verbose):
        view = parse_efibootmgr(efibootmgr_verbose)
        assert all(entry.active for entry in view.entries)

    def test_hints(self, efibootmgr_verbose):
        view = parse_efibootmgr(efibootmgr_verbose)
        hints = {entry.boot_id: entry.hint for entry in view.entries}
        assert hints["0004"] == "Windows"
        assert hints["0005"] == "Linux"
        assert hints["0000"] == ""
        assert hints["0001"] == ""
        assert hints["0002"] == ""
        assert hints["0003"] == ""

    def test_verbose_dp_and_data_lines_are_ignored(self, efibootmgr_verbose):
        view = parse_efibootmgr(efibootmgr_verbose)
        assert len(view.entries) == 6

    def test_plain_output_matches_verbose_output(self, efibootmgr_verbose, efibootmgr_plain):
        assert parse_efibootmgr(efibootmgr_plain) == parse_efibootmgr(efibootmgr_verbose)

    def test_boot_current_and_unknown_lines_are_ignored(self):
        view = parse_efibootmgr("BootCurrent: 0005\nTimeout: 1 seconds\nBootOrder: 0005\nBoot0005* Fedora\tHD(1)/\\EFI\\fedora\\shimx64.efi\n")
        assert view.order == ("0005",)
        assert len(view.entries) == 1

    def test_boot_next_line_is_ignored(self):
        view = parse_efibootmgr("BootNext: 0004\nBootOrder: 0005\nBoot0005* Fedora\tHD(1)/\\EFI\\fedora\\shimx64.efi\n")
        assert view.order == ("0005",)
        assert [entry.boot_id for entry in view.entries] == ["0005"]

    def test_inactive_entry_without_star(self):
        view = parse_efibootmgr("BootOrder: 0001\nBoot0001  Old Entry\t\\EFI\\old\\grubx64.efi\n")
        assert view.entries[0].active is False
        assert view.entries[0].hint == "Linux"

    def test_entry_without_path(self):
        view = parse_efibootmgr("BootOrder: 0001\nBoot0001* Bare Title\n")
        assert view.entries[0].title == "Bare Title"
        assert view.entries[0].path == ""

    def test_entry_not_in_order_is_dropped_from_entries(self):
        view = parse_efibootmgr("BootOrder: 0001\nBoot0001* One\t\\a\\shimx64.efi\nBoot0002* Two\t\\b\\shimx64.efi\n")
        assert [entry.boot_id for entry in view.entries] == ["0001"]

    def test_duplicate_order_ids_are_deduplicated(self):
        view = parse_efibootmgr("BootOrder: 0001,0001,0002\nBoot0001* One\t\\a\\shimx64.efi\nBoot0002* Two\t\\b\\shimx64.efi\n")
        assert view.order == ("0001", "0002")

    def test_malformed_boot_order_is_dropped(self):
        view = parse_efibootmgr("BootOrder: XYZW\nBoot0001* One\t\\a\\shimx64.efi\n")
        assert view.order == ()
        assert view.entries == ()

    def test_missing_boot_order(self):
        view = parse_efibootmgr("Boot0001* One\t\\a\\shimx64.efi\n")
        assert view.order == ()
        assert view.entries == ()

    def test_empty_text(self):
        view = parse_efibootmgr("")
        assert view.order == ()
        assert view.entries == ()

    def test_windows_entry_with_glued_bcd_blob(self, efibootmgr_verbose):
        # The real Windows entry has raw BCD bytes glued onto bootmgfw.efi;
        # the .efi cut in _loader_file must still recover the loader name.
        view = parse_efibootmgr(efibootmgr_verbose)
        windows = next(entry for entry in view.entries if entry.boot_id == "0004")
        assert windows.path.split("bootmgfw.efi", 1)[1] != ""
        assert windows.hint == "Windows"


class TestFirmwareMarks:
    def test_first_in_order_is_default(self, efibootmgr_verbose):
        view = parse_efibootmgr(efibootmgr_verbose)
        assert firmware_marks("0004", view) == ("DefaultBoot",)
        assert firmware_marks("0005", view) == ()

    def test_empty_order_marks_nothing(self):
        view = parse_efibootmgr("")
        assert firmware_marks("0004", view) == ()


class TestCheckBootId:
    @pytest.mark.parametrize("raw,expected", [
        ("0005", "0005"),
        ("00ab", "00AB"),
        ("ffff", "FFFF"),
    ])
    def test_valid(self, raw, expected):
        assert check_boot_id(raw) == expected

    @pytest.mark.parametrize("raw", ["", None, "000", "00005", "GGGG", "0 05", "-001"])
    def test_invalid(self, raw):
        with pytest.raises(ValueError):
            check_boot_id(raw)


class TestBootOrderWith:
    def test_moves_target_to_front(self):
        assert boot_order_with(EXPECTED_ORDER, "0005") == ("0005", "0004", "0001", "0000", "0003", "0002")

    def test_already_first(self):
        assert boot_order_with(EXPECTED_ORDER, "0004") == EXPECTED_ORDER

    def test_deduplicates(self):
        assert boot_order_with(("0001", "0002", "0001"), "0002") == ("0002", "0001")

    def test_accepts_lowercase(self):
        assert boot_order_with(("0001", "0002"), "000a") == ("000A", "0001", "0002")

    def test_empty_order_raises(self):
        with pytest.raises(ValueError):
            boot_order_with((), "0001")

    def test_invalid_target_raises(self):
        with pytest.raises(ValueError):
            boot_order_with(("0001",), "oops")

    def test_invalid_order_member_raises(self):
        with pytest.raises(ValueError):
            boot_order_with(("0001", "junk"), "0001")


class TestClassify:
    @pytest.mark.parametrize("text", [
        "HD(1,GPT,abc)/\\EFI\\Microsoft\\Boot\\bootmgfw.efi",
        "\\EFI\\MICROSOFT\\BOOT\\BOOTMGFW.EFI",
        "/EFI/Microsoft/Boot/bootmgfw.efi",
        "EFI\\Microsoft\\Boot\\bootmgfw.efi",
        "HD(1)/\\EFI\\some\\bootmgfw.efi",
        "File(\\EFI\\Microsoft\\Boot\\bootmgfw.efi)",
    ])
    def test_windows(self, text):
        assert _classify(text) == "Windows"

    @pytest.mark.parametrize("text", [
        "HD(1)/\\EFI\\fedora\\shimx64.efi",
        "HD(1)/\\EFI\\fedora\\shimaa64.efi",
        "HD(1)/\\EFI\\ubuntu\\grubx64.efi",
        "HD(1)/\\EFI\\systemd\\systemd-bootx64.efi",
        "File(\\efi\\ubuntu\\shimx64.efi)",
        "shimx64.efi extra arguments",
    ])
    def test_linux(self, text):
        assert _classify(text) == "Linux"

    @pytest.mark.parametrize("text", [
        "",
        "HD(1)/\\EFI\\BOOT\\BOOTX64.EFI",
        "PciRoot(0x0)/Pci(0x13,0x0)/Sata(1,0,0)",
        "EFI Network",
        "Windows Boot Manager",
    ])
    def test_unknown(self, text):
        assert _classify(text) == ""

    def test_glued_optional_data_is_cut_after_efi(self):
        # efibootmgr glues optional data (hex) onto the file path without a
        # separator; classification must see the bare loader name anyway.
        assert _classify("\\efi\\fedora\\shimx64.efi57494e") == "Linux"
        assert _classify("\\efi\\boot\\bootmgfw.efi57494e444f") == "Windows"


class TestHint:
    def test_path_wins_over_title(self):
        assert _hint("My Linux", "\\EFI\\Microsoft\\Boot\\bootmgfw.efi") == "Windows"

    def test_falls_back_to_title(self):
        assert _hint("shimx64.efi rescue", "") == "Linux"

    def test_neither(self):
        assert _hint("EFI Network", "PciRoot(0x0)/Sata(1,0,0)") == ""
