"""Ask whether to reboot into another firmware boot entry.

KDE uses kdialog. GNOME uses zenity. Every other desktop uses yad.
"""

from __future__ import annotations

import os
import shutil
import sys

from oswarp.actions import ActionError, read_firmware
from oswarp.dialogs import (
    ask_confirm,
    confirm_argv,
    interpret_confirm,
    run_dialog,
    show_alert,
    show_list,
)
from oswarp.elevate import FIRMWARE_SETUP, as_root
from oswarp.firmware import FirmwareEntry, FirmwareView, firmware_marks
from oswarp.packages import package_tips
from oswarp.config import (
    BOOT_NEXT,
    BOOT_ORDER,
    config_path,
    load_config,
    resolve_target,
    save_config,
)


def run_gui(name: str | None = None) -> int:
    if name is None:
        tool = find_dialog_tool()
        if tool is None:
            print("kdialog, yad, or zenity was not found.", file=sys.stderr)
            print("KDE: " + package_tips("kdialog"), file=sys.stderr)
            print("GNOME: " + package_tips("zenity"), file=sys.stderr)
            print("Other desktops: " + package_tips("yad"), file=sys.stderr)
            return 1
    else:
        tool = shutil.which(name)
        if tool is None:
            print(f"Could not find {name}.", file=sys.stderr)
            print(package_tips(name), file=sys.stderr)
            return 1
    if not _has_display():
        print("No display was found. OSWarp needs a graphical session.", file=sys.stderr)
        return 1
    return _session(tool)


def _has_display() -> bool:
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def find_dialog_tool() -> str | None:
    """Find the correct dialog tool to use for this desktop environment."""
    present = {}
    for name in ("yad", "kdialog", "zenity"):
        found = shutil.which(name)
        if found:
            present[name] = found
    choice = preferred_dialog(os.environ.get("XDG_CURRENT_DESKTOP", ""), set(present))
    if choice is None:
        return None
    return present[choice]


def preferred_dialog(desktop: str, present: set[str]) -> str | None:
    """KDE uses kdialog, GNOME uses zenity, and every other desktop uses yad."""
    names = {part.strip().lower() for part in desktop.split(":") if part.strip()}
    if "kde" in names:
        order = ("kdialog", "yad", "zenity")
    elif any(name == "gnome" or name.startswith("gnome-") for name in names):
        order = ("zenity", "yad", "kdialog")
    else:
        order = ("yad", "zenity", "kdialog")
    for name in order:
        if name in present:
            return name
    return None


def _session(tool: str) -> int:
    path = config_path()
    settings = load_config(path)
    boot = settings.boot
    saved_id = settings.saved_id

    if not boot: # No settings for BOOT_NEXT or BOOT_ORDER.
        chosen = _ask_boot(tool)
        if chosen is None:
            return 0 # No choice, exit.
        try:
            save_config(path, chosen, saved_id)
        except OSError as exc:
            show_alert(tool, f"The settings file could not be written.\n{path}\n{exc}", error=True)
            return 1
        boot = chosen

    try:
        view = read_firmware()
    except ActionError as exc:
        show_alert(tool, str(exc), error=True)
        return 1
    if not view.entries:
        show_alert(tool, "No firmware boot entries found in BootOrder.", error=True)
        return 1
    target = resolve_target(view.entries, saved_id, "Windows")
    if target is None:
        target = _pick(tool, view, can_return=False, boot=boot)
        if target is None:
            return 0 # No choice, exit.

    error = ""
    while True:
        choice = _confirm(tool, target, error, boot)
        error = "" # Clear last error.
        if choice == "cancel":
            return 0 # No choice, exit.
        if choice == "reboot":
            code, output = _reboot(target, boot)
            if code == 0:
                return 0
            error = output
            continue

        action = _config_menu(tool) # choice == "config"
        if action == "boot":
            boot = _change_boot(tool, boot)
            continue
        if action == "firmware":
            if not ask_confirm(tool, "Reboot into the firmware setup?"):
                continue
            code, output = as_root(None, FIRMWARE_SETUP)
            if code == 0:
                return 0
            error = output or "Did not reboot."
            continue
        if action == "entries":
            try:
                view = read_firmware()
            except ActionError as exc:
                show_alert(tool, str(exc), error=True)
                return 1
            picked = _pick(tool, view, can_return=True, boot=boot)
            if picked is not None:
                target = picked
        # Back from the list, or the config menu was cancelled: ask again.


def _config_menu(tool: str) -> str | None:
    text = "What do you want to change?"
    rows = (
        (_CONFIG_BOOT, "Boot method…"),
        (_CONFIG_ENTRIES, "Boot entry…"),
        (_CONFIG_FIRMWARE, "Firmware setup…"),
    )
    return show_list(tool, text, rows)


_CONFIG_BOOT = "boot"
_CONFIG_ENTRIES = "entries"
_CONFIG_FIRMWARE = "firmware"


def _ask_boot(tool: str, current: str = "") -> str | None:
    """Ask how the choice applies: permanent order or next boot only."""
    text = "Change the permanent boot order, or only the next boot?"
    rows = (
        (BOOT_NEXT, "Next boot only"),
        (BOOT_ORDER, "Permanent boot order"),
    )
    return show_list(tool, text, rows, current=current)


def _change_boot(tool: str, boot: str) -> str:
    path = config_path()
    chosen = _ask_boot(tool, boot)
    if chosen is None:
        return boot
    try:
        save_config(path, chosen, load_config(path).saved_id)
    except OSError as exc:
        show_alert(tool, f"The settings file could not be written.\n{path}\n{exc}", error=True)
        return boot
    return chosen


def _confirm(tool: str, target: FirmwareEntry, error: str, boot: str) -> str:
    lines = []
    if error:
        lines.append(error)
    else:
        lines.append(f"Reboot to {target.title}?")
    lines.append("")
    if boot == BOOT_NEXT:
        lines.append("This will change only the next boot.")
    else:
        lines.append("This will change the default boot order.")
    code, stdout, stderr = run_dialog(confirm_argv(tool, "\n".join(lines)))
    if code == 127:
        show_alert(tool, stderr or "Could not open the dialog.", error=True)
        return "cancel"
    return interpret_confirm(tool, code, stdout)


def _pick(tool: str, view: FirmwareView, can_return: bool, boot: str) -> FirmwareEntry | None:
    """Choose an entry and remember it. None means the list was cancelled."""
    rows = [(entry.boot_id, _row_label(entry, view)) for entry in view.entries]
    cancel = "Back" if can_return else "Quit"
    while True:
        boot_id = show_list(tool, _pick_intro(boot), rows, cancel, width=640, height=420)
        if boot_id is None: # Canceled.
            return None
        entry = next((item for item in view.entries if item.boot_id == boot_id), None)
        if entry is None: # Not found.
            return None
        if _remember_entry(tool, boot, entry.boot_id):
            return entry


def _remember_entry(tool: str, boot: str, boot_id: str) -> bool:
    path = config_path()
    try:
        save_config(path, boot, boot_id)
    except OSError as exc:
        show_alert(tool, f"The settings file could not be written.\n{path}\n{exc}", error=True)
        return False
    return True


def _pick_intro(boot: str) -> str:
    hint = "Next boot only" if boot == BOOT_NEXT else "Permanent boot order"
    return f"Choose the correct boot entry. ({hint})"


def _row_label(entry: FirmwareEntry, view: FirmwareView) -> str:
    marks = firmware_marks(entry.boot_id, view)
    title = entry.title or entry.boot_id
    if marks:
        title += " 〔" + " · ".join(marks) + "〕"
    bits = [f"Boot{entry.boot_id}"]
    if not entry.active:
        bits.append("Inactive")
    return _safe_label(title + " · " + " · ".join(bits))


def _reboot(target: FirmwareEntry, boot: str) -> tuple[int, str]:
    code, output = as_root(target.boot_id, boot)
    if code == 0:
        return 0, ""
    return code, output or "Did not reboot."


def _safe_label(text: str) -> str:
    if text.startswith("-"): # Prevent being parsed as an option.
        return "· " + text
    return text
