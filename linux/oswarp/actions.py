"""Privileged firmware actions."""

from __future__ import annotations

import shutil
import subprocess

from oswarp.packages import package_tips
from oswarp.firmware import (
    FirmwareEntry,
    FirmwareView,
    boot_order_with,
    check_boot_id,
    parse_efibootmgr,
)


class ActionError(Exception):
    pass


def read_firmware() -> FirmwareView:
    result = _efibootmgr("-v")
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise ActionError(detail or "efibootmgr could not read firmware boot entries.")
    return parse_efibootmgr(result.stdout or "")


def set_bootnext(boot_id: str) -> None:
    """Point this reboot at the entry just placed first."""
    match, _view = _require_entry(boot_id)
    result = _efibootmgr("-n", match.boot_id)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise ActionError(detail or "Could not set BootNext.")


def set_boot_order(boot_id: str) -> None:
    """Put the selected entry first in BootOrder and keep the rest."""
    match, view = _require_entry(boot_id)
    try:
        new_order = boot_order_with(view.order, match.boot_id)
    except ValueError:
        raise ActionError("Could not read the full boot order. Nothing was changed.") from None
    result = _efibootmgr("-o", ",".join(new_order))
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise ActionError(detail or "Could not set BootOrder.")


def reboot() -> None:
    systemctl = shutil.which("systemctl")
    if systemctl:
        command = [systemctl, "reboot"]
    else:
        shutdown = shutil.which("shutdown")
        if shutdown is None:
            raise ActionError("shutdown was not found.")
        command = [shutdown, "-r", "now"]
    try:
        result = subprocess.run(command, check=False, text=True, capture_output=True)
    except OSError as exc:
        raise ActionError(str(exc) or "Could not reboot.") from None
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise ActionError(detail or "Could not reboot.")


def _require_entry(boot_id: str) -> tuple[FirmwareEntry, FirmwareView]:
    try:
        boot_id = check_boot_id(boot_id)
    except ValueError:
        raise ActionError("The boot entry id is not valid.") from None
    view = read_firmware()
    match = next((item for item in view.entries if item.boot_id == boot_id), None)
    if match is None:
        raise ActionError("That boot entry is not in the list.")
    return match, view


def _efibootmgr(*args: str) -> subprocess.CompletedProcess[str]:
    tool = shutil.which("efibootmgr")
    if tool is None:
        raise ActionError("efibootmgr was not found. Please install it: " + package_tips("efibootmgr"))
    return subprocess.run([tool, *args], check=False, text=True, capture_output=True)
