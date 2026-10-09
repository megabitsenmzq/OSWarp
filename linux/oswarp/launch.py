"""Open the window, or headless when run by pkexec."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from oswarp.actions import ActionError, reboot, set_boot_order, set_bootnext


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    boot_id = _pkexec_boot_id(argv[1:])
    if boot_id is not None:
        return commit(boot_id)
    from oswarp.gui import run_gui

    return run_gui()


def commit(boot_id: str) -> int:
    """Move this entry first, set this reboot, and reboot."""
    try:
        set_boot_order(boot_id)
    except ActionError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    try:
        set_bootnext(boot_id)
        reboot()
    except ActionError as exc:
        print(
            "The boot order was changed, but the reboot did not happen.\n" + str(exc),
            file=sys.stderr,
        )
        return 1
    return 0


def _pkexec_boot_id(args: list[str]) -> str | None:
    """The window passes one boot id through pkexec."""
    if os.geteuid() == 0 and os.environ.get("PKEXEC_UID") and len(args) == 1:
        return args[0]
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


def _ensure_executable(path: Path) -> None:
    if os.access(path, os.X_OK):
        return
    try:
        os.chmod(path, 0o755)
    except OSError:
        pass


def _helper_path() -> Path:
    local = Path(__file__).resolve().parents[1] / "run.sh"
    if local.is_file():
        return local
    installed = Path("/usr/local/bin/oswarp")
    if installed.is_file():
        return installed
    raise SystemExit("Could not find run.sh.")
