"""Run the boot change as root through pkexec."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from oswarp.actions import ActionError, clear_bootnext, reboot, set_boot_order, set_bootnext
from oswarp.config import (
    BOOT_NEXT,
    BOOT_ORDER,
    config_path,
    save_config,
)


def as_root(boot_id: str, boot: str) -> tuple[int, str]:
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
        save_config(config_path(), boot, boot_id)
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


def _run_commit(boot_id: str, boot: str) -> tuple[int, str]:
    import io
    from contextlib import redirect_stderr, redirect_stdout

    out = io.StringIO()
    err = io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            code = commit(boot_id, boot)
    except SystemExit as exc:
        if not isinstance(exc.code, int):
            return 1, str(exc.code or "")
        code = exc.code
    except Exception as exc:
        return 1, str(exc)
    text = (out.getvalue() + err.getvalue()).strip()
    return code, text


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
    if boot != BOOT_ORDER: # Config is not BOOT_NEXT nor BOOT_ORDER.
        print("The boot setting is not valid.", file=sys.stderr)
        return 1
    try:
        set_boot_order(boot_id)
    except ActionError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    try:
        clear_bootnext() # Prevent boot next is different from the changed order.
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


def elevate_command(
    helper: Path,
    args: list[str],
    *,
    pkexec: str,
) -> list[str]:
    """Get the command to run the helper as root."""
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
    if local.is_file(): # If run.sh exists, it's in run once mode.
        return local
    installed = Path("/usr/local/bin/oswarp")
    if installed.is_file(): # Otherwise it's installed.
        return installed
    raise SystemExit("Could not find run.sh.")
