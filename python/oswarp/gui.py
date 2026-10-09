"""Ask whether to reboot into another firmware boot entry.

KDE uses kdialog. GNOME uses zenity. Every other desktop uses yad.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from oswarp.actions import ActionError, read_firmware
from oswarp.firmware import FirmwareEntry, FirmwareView, firmware_marks
from oswarp.launch import (
    _ensure_executable,
    _helper_path,
    commit,
    elevate_command,
    pkexec_bin,
)
from oswarp.packages import package_tips
from oswarp.target import load_saved_id, resolve_target, save_saved_id, target_path


def run_gui() -> int:
    tool = find_dialog_tool()
    if tool is None:
        print("kdialog, yad, or zenity was not found.", file=sys.stderr)
        print("KDE: " + package_tips("kdialog"), file=sys.stderr)
        print("GNOME: " + package_tips("zenity"), file=sys.stderr)
        print("Other desktops: " + package_tips("yad"), file=sys.stderr)
        return 1
    return _session(tool)


def find_dialog_tool() -> str | None:
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
    try:
        view = read_firmware()
    except ActionError as exc:
        _message(tool, str(exc), error=True)
        return 1
    if not view.entries:
        _message(tool, "No firmware boot entries.", error=True)
        return 1
    saved = load_saved_id(target_path())
    target = resolve_target(view.entries, saved, "Windows")
    if target is None:
        _pick(tool, view, can_return=False)
        return 0
    error = ""
    while True:
        choice = _confirm(tool, target, error)
        error = ""
        if choice == "cancel":
            return 0
        if choice == "reboot":
            code, output = _reboot(target)
            if code == 0:
                return 0
            error = output
            continue
        try:
            view = read_firmware()
        except ActionError as exc:
            _message(tool, str(exc), error=True)
            return 1
        if _pick(tool, view, can_return=True):
            return 0


def _confirm(tool: str, target: FirmwareEntry, error: str) -> str:
    lines = []
    if error:
        lines.append(error)
    else:
        lines.append(f"Reboot to {target.title}?")
    lines.append("")
    lines.append("This will change the default boot order.")
    code, stdout, stderr = _run_dialog(confirm_argv(tool, "\n".join(lines)))
    if code == 127:
        _message(tool, stderr or "Could not open the dialog.", error=True)
        return "cancel"
    return interpret_confirm(tool, code, stdout)


_REBOOT_LABEL = "Reboot"
_PICK_LABEL = "Choose entry"


def _icon_path() -> Path | None:
    candidate = Path(__file__).resolve().parents[1] / "Icon.png"
    if candidate.is_file():
        return candidate
    return None


def _icon_args(tool: str) -> list[str]:
    icon = _icon_path()
    if icon is None:
        return []
    if _tool_name(tool) == "kdialog":
        return ["--icon", str(icon)]
    return ["--window-icon", str(icon)]


def confirm_argv(tool: str, text: str) -> list[str]:
    if _tool_name(tool) == "kdialog":
        return [
            tool,
            "--title",
            "OSWarp",
            *_icon_args(tool),
            "--yes-label",
            _REBOOT_LABEL,
            "--no-label",
            _PICK_LABEL,
            "--cancel-label",
            "Cancel",
            "--yesnocancel",
            text,
        ]
    if _tool_name(tool) == "yad":
        # The first button is the default. Even exit codes print a result; odd ones do not.
        return [
            tool,
            "--title",
            "OSWarp",
            *_icon_args(tool),
            "--width",
            "480",
            "--center",
            "--no-markup",
            "--image",
            "dialog-question",
            "--button",
            _REBOOT_LABEL + ":0",
            "--button",
            _PICK_LABEL + ":2",
            "--button",
            "Cancel:1",
            "--text",
            text,
        ]
    return [
        tool,
        "--question",
        "--title",
        "OSWarp",
        *_icon_args(tool),
        "--width",
        "480",
        "--ok-label",
        _REBOOT_LABEL,
        "--cancel-label",
        "Cancel",
        "--extra-button",
        _PICK_LABEL,
        "--text",
        text,
    ]


def interpret_confirm(tool: str, code: int, stdout: str) -> str:
    if _tool_name(tool) == "kdialog":
        if code == 0:
            return "reboot"
        if code == 1:
            return "manual"
        return "cancel"
    if _tool_name(tool) == "yad":
        if code == 0:
            return "reboot"
        if code == 2:
            return "manual"
        return "cancel"
    if code == 0:
        return "reboot"
    if code == 1 and stdout.strip() == _PICK_LABEL:
        return "manual"
    return "cancel"


def _pick(tool: str, view: FirmwareView, can_return: bool) -> bool:
    """Change the permanent order and reboot. Cancel returns False."""
    intro = _pick_intro()
    rows = [(entry.boot_id, _row_label(entry, view)) for entry in view.entries]
    while True:
        code, stdout, stderr = _run_dialog(menu_argv(tool, intro, rows, can_return))
        if code == 127:
            _message(tool, stderr or "Could not open the list.", error=True)
            return False
        entry = interpret_menu(code, stdout, view.entries)
        if entry is None:
            return False
        changed, output = _as_root(entry.boot_id)
        if changed != 0:
            _message(tool, output or "The reboot did not finish.", error=True)
            continue
        return True


def _pick_intro() -> str:
    return "Choose the correct boot entry."


def _row_label(entry: FirmwareEntry, view: FirmwareView) -> str:
    marks = firmware_marks(entry.boot_id, view)
    title = entry.title or entry.boot_id
    if marks:
        title += "    〔" + " · ".join(marks) + "〕"
    bits = [f"Boot{entry.boot_id}"]
    if not entry.active:
        bits.append("Inactive")
    return _safe_label(title + "  ·  " + "  ·  ".join(bits))


def menu_argv(
    tool: str,
    intro: str,
    rows: list[tuple[str, str]],
    can_return: bool,
) -> list[str]:
    cancel = "Back" if can_return else "Quit"
    if _tool_name(tool) == "kdialog":
        command = [
            tool,
            "--title",
            "OSWarp",
            *_icon_args(tool),
            "--cancel-label",
            cancel,
            "--menu",
            intro,
        ]
        for boot_id, label in rows:
            command.extend([boot_id, label])
        return command
    if _tool_name(tool) == "yad":
        # OK is an even code so the selected id is printed. Back/Quit is odd.
        command = [
            tool,
            "--list",
            "--title",
            "OSWarp",
            *_icon_args(tool),
            "--width",
            "640",
            "--height",
            "420",
            "--center",
            "--no-markup",
            "--button",
            "OK:0",
            "--button",
            cancel + ":1",
            "--text",
            intro,
            "--column",
            "Id",
            "--column",
            "Entry",
            "--hide-column",
            "1",
            "--print-column",
            "1",
            "--search-column",
            "2",
            "--no-headers",
        ]
        for boot_id, label in rows:
            command.extend([boot_id, label])
        return command
    command = [
        tool,
        "--list",
        "--title",
        "OSWarp",
        *_icon_args(tool),
        "--width",
        "640",
        "--height",
        "420",
        "--ok-label",
        "OK",
        "--cancel-label",
        cancel,
        "--text",
        intro,
        "--column",
        "Id",
        "--column",
        "Entry",
        "--hide-column",
        "1",
        "--print-column",
        "1",
        "--hide-header",
    ]
    for boot_id, label in rows:
        command.extend([boot_id, label])
    return command


def interpret_menu(
    code: int,
    stdout: str,
    entries: list[FirmwareEntry],
) -> FirmwareEntry | None:
    if code != 0 or not stdout.strip():
        return None
    boot_id = stdout.strip().splitlines()[0].strip()
    for entry in entries:
        if entry.boot_id == boot_id:
            return entry
    return None


def _reboot(target: FirmwareEntry) -> tuple[int, str]:
    code, output = _as_root(target.boot_id)
    if code == 0:
        return 0, ""
    return code, output or "Did not reboot."


def _message(tool: str, text: str, error: bool) -> None:
    _run_dialog(message_argv(tool, text, error))


def message_argv(tool: str, text: str, error: bool) -> list[str]:
    if _tool_name(tool) == "kdialog":
        return [tool, "--title", "OSWarp", "--error" if error else "--msgbox", text]
    if _tool_name(tool) == "yad":
        return [
            tool,
            "--title",
            "OSWarp",
            "--width",
            "460",
            "--center",
            "--no-markup",
            "--image",
            "dialog-error" if error else "dialog-information",
            "--button",
            "OK:0",
            "--text",
            text,
        ]
    return [
        tool,
        "--error" if error else "--info",
        "--title",
        "OSWarp",
        "--width",
        "460",
        "--text",
        text,
    ]


def _run_dialog(argv: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(argv, text=True, capture_output=True)
    return result.returncode, result.stdout or "", (result.stderr or "").strip()


def _as_root(boot_id: str) -> tuple[int, str]:
    save_note = _save_choice(boot_id)
    if os.geteuid() == 0:
        code, output = _run_commit(boot_id)
    else:
        try:
            helper = _helper_path()
            _ensure_executable(helper)
            command = elevate_command(helper, [boot_id], pkexec=pkexec_bin())
        except SystemExit as exc:
            code, output = 1, str(exc)
        else:
            result = subprocess.run(command, text=True, capture_output=True)
            code = result.returncode
            output = _explain_root((result.stdout or "") + (result.stderr or ""), code)
    if code == 0:
        return 0, ""
    if save_note:
        output = f"{output}\n{save_note}".strip() if output else save_note
    return code, output


def _save_choice(boot_id: str) -> str:
    try:
        save_saved_id(target_path(), boot_id)
    except OSError as exc:
        return f"The choice could not be saved: {exc}"
    return ""


def _explain_root(output: str, code: int = 1) -> str:
    text = output.strip()
    low = text.lower()
    if code == 126:
        return "Authorization was cancelled. Boot entries were not changed."
    if "no authentication agent" in low:
        detail = text or "No authentication agent found."
        return "No authentication agent was found. Boot entries were not changed.\n" + detail
    if "not authorized" in low or "authentication failed" in low:
        detail = text or "Not authorized"
        return "Authorization did not finish. Boot entries were not changed.\n" + detail
    return text


def _run_commit(boot_id: str) -> tuple[int, str]:
    import io
    from contextlib import redirect_stderr, redirect_stdout

    out = io.StringIO()
    err = io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            code = commit(boot_id)
    except SystemExit as exc:
        code = int(exc.code or 0)
    except Exception as exc:
        return 1, str(exc)
    text = (out.getvalue() + err.getvalue()).strip()
    return code, text


def _tool_name(tool: str) -> str:
    return Path(tool).name


def _safe_label(text: str) -> str:
    cleaned = " ".join(text.split())
    if cleaned.startswith("-"):
        return "· " + cleaned
    return cleaned
