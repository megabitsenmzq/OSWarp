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
    ensure_executable,
    helper_path,
    commit,
    elevate_command,
    pkexec_bin,
)
from oswarp.packages import package_tips
from oswarp.target import (
    BOOT_NEXT,
    BOOT_ORDER,
    TargetError,
    load_target,
    resolve_target,
    save_target,
    target_config_path,
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
    path = target_config_path()
    try:
        settings = load_target(path)
    except TargetError as exc:
        _message(tool, str(exc), error=True)
        return 1
    boot = settings.boot
    saved_id = settings.saved_id
    if not boot:
        chosen = _ask_boot(tool)
        if chosen is None:
            return 0
        try:
            save_target(path, chosen, saved_id)
        except OSError as exc:
            _message(tool, f"The settings file could not be written.\n{path}\n{exc}", error=True)
            return 1
        boot = chosen
    try:
        view = read_firmware()
    except ActionError as exc:
        _message(tool, str(exc), error=True)
        return 1
    if not view.entries:
        _message(tool, "No firmware boot entries.", error=True)
        return 1
    target = resolve_target(view.entries, saved_id, "Windows")
    if target is None:
        _pick(tool, view, can_return=False, boot=boot)
        return 0
    error = ""
    while True:
        choice = _confirm(tool, target, error, boot)
        error = ""
        if choice == "cancel":
            return 0
        if choice == "reboot":
            code, output = _reboot(target, boot)
            if code == 0:
                return 0
            error = output
            continue
        try:
            view = read_firmware()
        except ActionError as exc:
            _message(tool, str(exc), error=True)
            return 1
        finished, boot = _pick(tool, view, can_return=True, boot=boot)
        if finished:
            return 0


def _ask_boot(tool: str) -> str | None:
    text = "Change the permanent boot order, or only the next boot?"
    code, stdout, stderr = _run_dialog(boot_argv(tool, text))
    if code == 127:
        _message(tool, stderr or "Could not open the dialog.", error=True)
        return None
    return interpret_boot(code, stdout)


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
    code, stdout, stderr = _run_dialog(confirm_argv(tool, "\n".join(lines)))
    if code == 127:
        _message(tool, stderr or "Could not open the dialog.", error=True)
        return "cancel"
    return interpret_confirm(tool, code, stdout)


_REBOOT_LABEL = "Reboot"
_PICK_LABEL = "Choose entry"
_BOOT_METHOD = "Boot method"
_BOOT_METHOD_ID = "boot-method"


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


def boot_argv(tool: str, text: str) -> list[str]:
    choices = (
        (BOOT_ORDER, "Permanent boot order"),
        (BOOT_NEXT, "Next boot only"),
    )
    if _tool_name(tool) == "kdialog":
        command = [
            tool,
            "--title",
            "OSWarp",
            *_icon_args(tool),
            "--default",
            "Permanent boot order",
            "--menu",
            text,
        ]
        for value, label in choices:
            command.extend([value, label])
        return command
    columns = [
        "--column",
        "Pick",
        "--column",
        "Id",
        "--column",
        "Choice",
        "--hide-column",
        "2",
        "--print-column",
        "2",
    ]
    if _tool_name(tool) == "yad":
        command = [
            tool,
            "--list",
            "--radiolist",
            "--title",
            "OSWarp",
            *_icon_args(tool),
            "--width",
            "480",
            "--height",
            "320",
            "--center",
            "--no-markup",
            "--button",
            "OK:0",
            "--button",
            "Cancel:1",
            "--separator=",
            "--text",
            text,
            *columns,
            "--no-headers",
        ]
    else:
        command = [
            tool,
            "--list",
            "--radiolist",
            "--title",
            "OSWarp",
            *_icon_args(tool),
            "--width",
            "480",
            "--height",
            "320",
            "--text",
            text,
            *columns,
            "--hide-header",
        ]
    for value, label in choices:
        selected = "TRUE" if value == BOOT_ORDER else "FALSE"
        command.extend([selected, value, label])
    return command


def interpret_boot(code: int, stdout: str) -> str | None:
    if code != 0 or not stdout.strip():
        return None
    value = stdout.strip().splitlines()[0].strip()
    if value in (BOOT_ORDER, BOOT_NEXT):
        return value
    return None


def _pick(tool: str, view: FirmwareView, can_return: bool, boot: str) -> tuple[bool, str]:
    """Reboot, or return the boot mode when the list is cancelled."""
    rows = [(entry.boot_id, _row_label(entry, view)) for entry in view.entries]
    while True:
        intro = _pick_intro(boot)
        code, stdout, stderr = _run_dialog(menu_argv(tool, intro, rows, can_return))
        if code == 127:
            _message(tool, stderr or "Could not open the list.", error=True)
            return False, boot
        if menu_choice(tool, code, stdout) == "boot":
            boot = _change_boot(tool, boot)
            continue
        entry = interpret_menu(code, stdout, view.entries)
        if entry is None:
            return False, boot
        changed, output = _as_root(entry.boot_id, boot)
        if changed != 0:
            _message(tool, output or "The reboot did not finish.", error=True)
            continue
        return True, boot


def _change_boot(tool: str, boot: str) -> str:
    path = target_config_path()
    chosen = _ask_boot(tool)
    if chosen is None:
        return boot
    try:
        settings = load_target(path)
    except TargetError as exc:
        _message(tool, str(exc), error=True)
        return boot
    try:
        save_target(path, chosen, settings.saved_id)
    except OSError as exc:
        _message(tool, f"The settings file could not be written.\n{path}\n{exc}", error=True)
        return boot
    return chosen


def _pick_intro(boot: str) -> str:
    hint = "Next boot only" if boot == BOOT_NEXT else "Permanent boot order"
    return f"Choose the correct boot entry. ({hint})"


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
        # kdialog menus have no extra buttons, so the boot method is a menu row.
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
        command.extend([_BOOT_METHOD_ID, _BOOT_METHOD + "…"])
        for boot_id, label in rows:
            command.extend([boot_id, label])
        return command
    if _tool_name(tool) == "yad":
        # Yad prints the row only for an even exit code. OK is 0. Boot method
        # is 3 and Back/Quit is 1, so those clicks print nothing.
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
            _BOOT_METHOD + ":3",
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
            "--separator=",
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
        "--extra-button",
        _BOOT_METHOD,
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


def menu_choice(tool: str, code: int, stdout: str) -> str:
    """ok, boot, or cancel. On kdialog the boot choice is a menu row."""
    name = _tool_name(tool)
    if name == "yad" and code == 3:
        return "boot"
    if name == "zenity" and code == 1 and stdout.strip() == _BOOT_METHOD:
        return "boot"
    if code == 0 and stdout.strip():
        if name == "kdialog" and stdout.strip() == _BOOT_METHOD_ID:
            return "boot"
        return "ok"
    return "cancel"


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


def _reboot(target: FirmwareEntry, boot: str) -> tuple[int, str]:
    code, output = _as_root(target.boot_id, boot)
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
    try:
        result = subprocess.run(argv, text=True, capture_output=True)
    except OSError as exc:
        return 127, "", str(exc)
    return result.returncode, result.stdout or "", (result.stderr or "").strip()


def _as_root(boot_id: str, boot: str) -> tuple[int, str]:
    path = target_config_path()
    try:
        backup = _read_target(path)
    except OSError as exc:
        return 1, f"The settings file could not be read.\n{path}\n{exc}"
    save_note = _save_choice(boot_id, boot)
    if os.geteuid() == 0:
        code, output = _run_commit(boot_id, boot)
    else:
        code, output = _elevate_commit(boot_id, boot)
    if code == 0:
        return 0, ""
    if save_note:
        output = f"{output}\n{save_note}".strip() if output else save_note
        return code, output
    restore_note = _restore_target(path, backup)
    if restore_note:
        output = f"{output}\n{restore_note}".strip() if output else restore_note
    return code, output


def _elevate_commit(boot_id: str, boot: str) -> tuple[int, str]:
    try:
        helper = helper_path()
        ensure_executable(helper)
        command = elevate_command(helper, [boot_id, boot], pkexec=pkexec_bin())
    except SystemExit as exc:
        return 1, str(exc)
    try:
        result = subprocess.run(command, text=True, capture_output=True)
    except OSError as exc:
        return 1, str(exc)
    return result.returncode, _explain_root(
        (result.stdout or "") + (result.stderr or ""), result.returncode
    )


def _save_choice(boot_id: str, boot: str) -> str:
    try:
        save_target(target_config_path(), boot, boot_id)
    except OSError as exc:
        return f"The choice could not be saved: {exc}"
    return ""


def _read_target(path: Path) -> bytes | None:
    """Return the previous content. None means the file does not exist."""
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def _restore_target(path: Path, backup: bytes | None) -> str:
    try:
        if backup is None:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        else:
            path.write_bytes(backup)
    except OSError as exc:
        return f"The previous choice could not be restored: {exc}"
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


def _run_commit(boot_id: str, boot: str) -> tuple[int, str]:
    import io
    from contextlib import redirect_stderr, redirect_stdout

    out = io.StringIO()
    err = io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            code = commit(boot_id, boot)
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
