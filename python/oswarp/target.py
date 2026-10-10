"""Remember the chosen firmware entry and decide which one to offer."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from oswarp.firmware import FirmwareEntry, check_boot_id

BOOT_ORDER = "bootorder"
BOOT_NEXT = "bootnext"
_BOOT_VALUES = (BOOT_ORDER, BOOT_NEXT)


class TargetError(Exception):
    """The settings file is present but not usable."""


@dataclass(frozen=True)
class TargetSettings:
    boot: str
    saved_id: str


def config_home() -> Path:
    configured = os.environ.get("XDG_CONFIG_HOME")
    if configured:
        return Path(configured)
    return Path.home() / ".config"


def target_config_path() -> Path:
    return config_home() / "oswarp" / "target"


def load_target(path: Path) -> TargetSettings:
    """Read boot= and id=."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return TargetSettings(boot="", saved_id="")
    except (OSError, UnicodeError) as exc:
        raise TargetError(_settings_error(path, str(exc))) from None
    if text.endswith("\n"):
        text = text[:-1]
    lines = []
    for line in text.split("\n"):
        line = line.strip()
        if line == "":
            continue
        lines.append(line)
    if not lines:
        return TargetSettings(boot="", saved_id="")
    if len(lines) == 1 and "=" not in lines[0]:
        try:
            return TargetSettings(boot="", saved_id=check_boot_id(lines[0]))
        except ValueError:
            raise TargetError(_settings_error(path)) from None
    boot = ""
    saved_id = ""
    seen: set[str] = set()
    for line in lines:
        if "=" not in line:
            raise TargetError(_settings_error(path))
        key, value = line.split("=", 1)
        if key in seen or key not in ("boot", "id"):
            raise TargetError(_settings_error(path))
        seen.add(key)
        if key == "boot":
            value = value.lower()
            if value not in _BOOT_VALUES:
                raise TargetError(_settings_error(path))
            boot = value
        else:
            try:
                saved_id = check_boot_id(value)
            except ValueError:
                raise TargetError(_settings_error(path)) from None
    return TargetSettings(boot=boot, saved_id=saved_id)


def save_target(path: Path, boot: str, saved_id: str) -> None:
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


def _settings_error(path: Path, detail: str = "") -> str:
    text = "The settings file could not be read.\n" + str(path)
    text += "\nUse boot=bootorder or boot=bootnext."
    if detail:
        text += "\n" + detail
    return text


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
