"""Get tip text for a missing package."""

import shutil


def package_tips(
    package: str,
    *,
    has_apt: bool | None = None,
    has_dnf: bool | None = None,
    has_pacman: bool | None = None,
) -> str:
    """Get tip text for a missing package."""
    if has_apt is None:
        has_apt = shutil.which("apt-get") is not None
    if has_dnf is None:
        has_dnf = shutil.which("dnf") is not None
    if has_pacman is None:
        has_pacman = shutil.which("pacman") is not None
    if has_apt:
        return "sudo apt install " + package
    if has_dnf:
        return "sudo dnf install " + package
    if has_pacman:
        return "sudo pacman -S " + package
    return "Please install " + package
