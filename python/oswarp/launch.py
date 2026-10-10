"""Open the window, or headless when run by pkexec."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from oswarp.actions import ActionError, clear_bootnext, reboot, set_boot_order, set_bootnext
from oswarp.target import BOOT_NEXT, BOOT_ORDER


_DIALOG_TOOLS = ("kdialog", "zenity", "yad")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    request = _pkexec_boot(argv[1:])
    if request is not None:
        return commit(request[0], request[1])
    from oswarp.gui import run_gui

    return run_gui(_requested_dialog(argv[1:]))


def _requested_dialog(args: list[str]) -> str | None:
    """Check whether a dialog tool was passed in."""
    if len(args) == 1 and args[0] in _DIALOG_TOOLS:
        return args[0]
    return None


def commit(boot_id: str, boot: str) -> int:
    """Change the chosen firmware setting, then reboot."""
    if boot == BOOT_NEXT:
        try:
            set_bootnext(boot_id)
        except ActionError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        try:
            reboot()
        except ActionError as exc:
            print(
                "The next boot was changed, but the reboot did not happen.\n" + str(exc),
                file=sys.stderr,
            )
            return 1
        return 0
    if boot != BOOT_ORDER:
        print("The boot setting is not valid.", file=sys.stderr)
        return 1
    try:
        set_boot_order(boot_id)
    except ActionError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    try:
        clear_bootnext()
    except ActionError as exc:
        print(
            "The boot order was changed, but the next-boot setting could not be cleared.\n" + str(exc),
            file=sys.stderr,
        )
        return 1
    try:
        reboot()
    except ActionError as exc:
        print(
            "The boot order was changed, but the reboot did not happen.\n" + str(exc),
            file=sys.stderr,
        )
        return 1
    return 0


def _pkexec_boot(args: list[str]) -> tuple[str, str] | None:
    if os.geteuid() == 0 and os.environ.get("PKEXEC_UID") and len(args) == 2:
        if args[1] in (BOOT_ORDER, BOOT_NEXT):
            return args[0], args[1]
    return None


def elevate_command(
    helper: Path,
    args: list[str],
    *,
    pkexec: str,
) -> list[str]:
    """Ask the system agent to run the helper as root."""
    return [pkexec, str(helper), *args]


def pkexec_bin() -> str:
    found = shutil.which("pkexec")
    if found is None:
        raise SystemExit("Could not find pkexec.")
    return found


def ensure_executable(path: Path) -> None:
    if os.access(path, os.X_OK):
        return
    try:
        os.chmod(path, 0o755)
    except OSError:
        pass


def helper_path() -> Path:
    local = Path(__file__).resolve().parents[1] / "run.sh"
    if local.is_file():
        return local
    installed = Path("/usr/local/bin/oswarp")
    if installed.is_file():
        return installed
    raise SystemExit("Could not find run.sh.")
