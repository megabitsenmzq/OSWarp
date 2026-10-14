"""Build the kdialog, zenity, and yad commands, and read what they return."""

from __future__ import annotations

import subprocess
from pathlib import Path


_REBOOT_LABEL = "Reboot"
_CONFIG_LABEL = "Config"


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
            _CONFIG_LABEL,
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
            _CONFIG_LABEL + ":2",
            "--button",
            "Cancel:1",
            "--text",
            text,
        ]
    return [
        tool,
        "--question",
        "--no-markup",
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
        _CONFIG_LABEL,
        "--text",
        text,
    ]


def interpret_confirm(tool: str, code: int, stdout: str) -> str:
    if _tool_name(tool) == "kdialog":
        if code == 0:
            return "reboot"
        if code == 1:
            return "config"
        return "cancel"
    if _tool_name(tool) == "yad":
        if code == 0:
            return "reboot"
        if code == 2:
            return "config"
        return "cancel"
    # Some version of zenity also use code 0 for the extra button.
    if stdout.strip() == _CONFIG_LABEL:
        return "config"
    if code == 0:
        return "reboot"
    return "cancel"


def list_argv(
    tool: str,
    intro: str,
    rows: list[tuple[str, str]],
    cancel: str = "Cancel",
    width: int = 560,
    height: int = 360,
    current: str = "",
) -> list[str]:
    name = _tool_name(tool)
    if name == "kdialog":
        command = [
            tool,
            "--title",
            "OSWarp",
            *_icon_args(tool),
            "--cancel-label",
            cancel,
        ]
        # kdialog matches --default against the label, not the id.
        default_label = next((text for row_id, text in rows if row_id == current), None)
        if default_label is not None:
            command.extend(["--default", default_label])
        command.extend(["--menu", intro])
        for row_id, label in rows:
            command.extend([row_id, label])
        return command
    command = [
        tool,
        "--list",
        "--title",
        "OSWarp",
        *_icon_args(tool),
        "--width",
        str(width),
        "--height",
        str(height),
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
    ]
    if name == "yad":
        # Yad prints the row only for an even exit code; OK is 0 and cancel is 1.
        command.extend(
            [
                "--center",
                "--no-markup",
                "--button",
                "OK:0",
                "--button",
                cancel + ":1",
                "--separator=",
                "--search-column",
                "2",
                "--no-headers",
            ]
        )
    else:
        command.extend(
            ["--no-markup", "--ok-label", "OK", "--cancel-label", cancel, "--hide-header"]
        )
    for row_id, label in rows:
        command.extend([row_id, label])
    return command


def show_list(
    tool: str,
    intro: str,
    rows: list[tuple[str, str]],
    cancel: str = "Cancel",
    width: int = 560,
    height: int = 360,
    current: str = "",
) -> str | None:
    """Show a list dialog and return the chosen row id. None means no choice."""
    code, stdout, stderr = run_dialog(list_argv(tool, intro, rows, cancel, width, height, current))
    if code == 127:
        show_alert(tool, stderr or "Could not open the list.", error=True)
        return None
    if code != 0 or not stdout.strip():
        return None
    return stdout.strip().splitlines()[0].strip()


def show_alert(tool: str, text: str, error: bool = False) -> None:
    run_dialog(alert_argv(tool, text, error))


def alert_argv(tool: str, text: str, error: bool) -> list[str]:
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
        "--no-markup",
        "--title",
        "OSWarp",
        "--width",
        "460",
        "--text",
        text,
    ]


def run_dialog(argv: list[str]) -> tuple[int, str, str]:
    try:
        result = subprocess.run(argv, text=True, capture_output=True)
    except OSError as exc:
        return 127, "", str(exc)
    return result.returncode, result.stdout or "", (result.stderr or "").strip()


def ask_confirm(tool: str, text: str) -> bool:
    code, _stdout, stderr = run_dialog(_ask_confirm_argv(tool, text))
    if code == 127:
        show_alert(tool, stderr or "Could not open the dialog.", error=True)
        return False
    return code == 0


def _ask_confirm_argv(tool: str, text: str) -> list[str]:
    name = _tool_name(tool)
    if name == "kdialog":
        return [
            tool,
            "--title",
            "OSWarp",
            *_icon_args(tool),
            "--yes-label",
            _REBOOT_LABEL,
            "--no-label",
            "Cancel",
            "--yesno",
            text,
        ]
    if name == "yad":
        return [
            tool,
            "--title",
            "OSWarp",
            *_icon_args(tool),
            "--width",
            "420",
            "--center",
            "--no-markup",
            "--image",
            "dialog-question",
            "--button",
            _REBOOT_LABEL + ":0",
            "--button",
            "Cancel:1",
            "--text",
            text,
        ]
    return [
        tool,
        "--question",
        "--no-markup",
        "--title",
        "OSWarp",
        *_icon_args(tool),
        "--width",
        "420",
        "--ok-label",
        _REBOOT_LABEL,
        "--cancel-label",
        "Cancel",
        "--text",
        text,
    ]


def _tool_name(tool: str) -> str:
    return Path(tool).name
