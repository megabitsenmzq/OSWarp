"""Read and write the OSWarp config, and decide which entry to offer."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from oswarp.firmware import FirmwareEntry, check_boot_id

BOOT_ORDER = "bootorder"
BOOT_NEXT = "bootnext"
_BOOT_VALUES = (BOOT_ORDER, BOOT_NEXT)


@dataclass(frozen=True)
class Config:
    boot: str
    saved_id: str


def config_home() -> Path:
    configured = os.environ.get("XDG_CONFIG_HOME")
    if configured:
        return Path(configured)
    return Path.home() / ".config"


def config_path() -> Path:
    return config_home() / "oswarp" / "config"


def load_config(path: Path) -> Config:
    """Read boot= and id= from the config file."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return Config(boot="", saved_id="")
    if text.endswith("\n"):
        text = text[:-1]

    lines = []
    for line in text.split("\n"):
        line = line.strip()
        if line == "":
            continue
        lines.append(line)
    if not lines:
        return Config(boot="", saved_id="")

    boot = ""
    saved_id = ""
    seen: set[str] = set()
    for line in lines:
        if "=" not in line:
            return Config(boot="", saved_id="")
        key, value = line.split("=", 1)
        if key in seen or key not in ("boot", "id"):
            return Config(boot="", saved_id="")
        seen.add(key)
        if key == "boot":
            value = value.lower()
            if value not in _BOOT_VALUES:
                return Config(boot="", saved_id="")
            boot = value
        else:
            try:
                saved_id = check_boot_id(value)
            except ValueError:
                return Config(boot="", saved_id="")
    return Config(boot=boot, saved_id=saved_id)


def save_config(path: Path, boot: str, saved_id: str) -> None:
    if boot not in _BOOT_VALUES:
        raise ValueError(boot)
    lines = ["boot=" + boot]
    if saved_id:
        lines.append("id=" + check_boot_id(saved_id))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def resolve_target(
    entries: tuple[FirmwareEntry, ...] | list[FirmwareEntry],
    saved_id: str,
    hint: str, # Windows
) -> FirmwareEntry | None:
    """Use the saved id when it is still listed. Otherwise rematch."""
    if saved_id:
        for entry in entries:
            if entry.boot_id == saved_id:
                return entry

    # Find new entry by hint.
    matches = [entry for entry in entries if entry.hint == hint]
    if len(matches) == 1:
        return matches[0]
    return None
