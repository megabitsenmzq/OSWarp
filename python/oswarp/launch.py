"""Open the window, or run headless when called by pkexec."""

from __future__ import annotations

import os
import sys

from oswarp.elevate import commit
from oswarp.config import BOOT_NEXT, BOOT_ORDER


_DIALOG_TOOLS = ("kdialog", "zenity", "yad")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    request = _pkexec_boot(argv[1:])
    if request is not None: # Called by pkexec.
        return commit(request[0], request[1])
    from oswarp.gui import run_gui

    return run_gui(_requested_dialog(argv[1:]))


def _requested_dialog(args: list[str]) -> str | None:
    """Check whether a dialog tool was passed in."""
    if len(args) == 1 and args[0] in _DIALOG_TOOLS:
        return args[0]
    return None


def _pkexec_boot(args: list[str]) -> tuple[str, str] | None:
    """Make sure called by pkexec. uid=0(root), has env, has args."""
    if os.geteuid() == 0 and os.environ.get("PKEXEC_UID") and len(args) == 2:
        if args[1] in (BOOT_ORDER, BOOT_NEXT):
            return args[0], args[1]
    return None
