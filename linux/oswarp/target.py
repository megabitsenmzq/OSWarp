"""Remember the chosen firmware entry and decide which one to offer."""

from __future__ import annotations

import os
from pathlib import Path

from oswarp.firmware import FirmwareEntry, check_boot_id


def config_home() -> Path:
    configured = os.environ.get("XDG_CONFIG_HOME")
    if configured:
        return Path(configured)
    return Path.home() / ".config"


def target_path() -> Path:
    return config_home() / "oswarp" / "target"


def load_saved_id(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    lines = text.splitlines()
    if not lines:
        return ""
    try:
        return check_boot_id(lines[0].strip())
    except ValueError:
        return ""


def save_saved_id(path: Path, boot_id: str) -> None:
    boot_id = check_boot_id(boot_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(boot_id + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def resolve_target(
    entries: tuple[FirmwareEntry, ...] | list[FirmwareEntry],
    saved_id: str,
    hint: str,
) -> FirmwareEntry | None:
    """Use the saved id when it is still listed. Otherwise rematch."""
    if saved_id:
        for entry in entries:
            if entry.boot_id == saved_id:
                return entry
    matches = [entry for entry in entries if entry.hint == hint and entry.active]
    if len(matches) == 1:
        return matches[0]
    return None
