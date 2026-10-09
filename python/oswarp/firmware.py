"""Read firmware boot entries. Parses efibootmgr output."""

from __future__ import annotations

import re
from dataclasses import dataclass

_ENTRY = re.compile(r"^Boot([0-9A-Fa-f]{4})(\*?)\s+(.*)$")


@dataclass(frozen=True)
class FirmwareEntry:
    boot_id: str
    title: str
    path: str
    active: bool
    hint: str


@dataclass(frozen=True)
class FirmwareView:
    order: tuple[str, ...]
    entries: tuple[FirmwareEntry, ...]


def firmware_marks(boot_id: str, view: FirmwareView) -> tuple[str, ...]:
    if view.order and boot_id == view.order[0]:
        return ("DefaultBoot",)
    return ()


def parse_efibootmgr(text: str) -> FirmwareView:
    order: list[str] = []
    entries: list[FirmwareEntry] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("BootOrder:"):
            try:
                order = _parse_order(line.split(":", 1)[1])
            except ValueError:
                order = []
            continue
        match = _ENTRY.match(line)
        if match is None:
            continue
        boot_id, star, rest = match.group(1).upper(), match.group(2), match.group(3)
        title, path = _split_title(rest)
        entries.append(
            FirmwareEntry(
                boot_id=boot_id,
                title=title,
                path=path,
                active=star == "*",
                hint=_hint(title, path),
            )
        )
    return FirmwareView(
        order=tuple(order),
        entries=tuple(entries),
    )


def boot_order_with(order: tuple[str, ...], boot_id: str) -> tuple[str, ...]:
    """Move boot_id to the front and keep every previous entry."""
    boot_id = check_boot_id(boot_id)
    if not order:
        raise ValueError("empty")
    cleaned: list[str] = []
    for item in order:
        item = check_boot_id(item)
        if item not in cleaned:
            cleaned.append(item)
    rest = [item for item in cleaned if item != boot_id]
    return (boot_id, *rest)


def check_boot_id(boot_id: str) -> str:
    if not re.fullmatch(r"[0-9A-Fa-f]{4}", boot_id or ""):
        raise ValueError(boot_id)
    return boot_id.upper()


def _parse_order(text: str) -> list[str]:
    order: list[str] = []
    for part in text.split(","):
        part = part.strip().upper()
        if not part:
            continue
        if not re.fullmatch(r"[0-9A-F]{4}", part):
            raise ValueError(part)
        if part not in order:
            order.append(part)
    return order


def _split_title(rest: str) -> tuple[str, str]:
    if "\t" in rest:
        title, path = rest.split("\t", 1)
        return title.strip(), path.strip()
    return rest.strip(), ""


def _hint(title: str, path: str) -> str:
    """Classify by the loader path.."""
    found = _classify(path)
    if found:
        return found
    return _classify(title)


def _classify(text: str) -> str:
    if not text:
        return ""
    folded = text.replace("/", "\\").lower()
    if "\\efi\\microsoft\\" in folded or folded.startswith("efi\\microsoft\\"):
        return "Windows"
    if "\\efi\\openbsd\\" in folded or folded.startswith("efi\\openbsd\\"):
        return "OpenBSD"
    if "\\efi\\freebsd\\" in folded or folded.startswith("efi\\freebsd\\"):
        return "FreeBSD"
    file_name = _loader_file(folded)
    if file_name == "bootmgfw.efi":
        return "Windows"
    if not file_name.endswith(".efi"):
        return ""
    if file_name.startswith(("shim", "grub", "systemd-boot")):
        return "Linux"
    return ""


def _loader_file(folded: str) -> str:
    file_name = folded.rsplit("\\", 1)[-1]
    return file_name.split(" ", 1)[0]
