from oswarp.packages import package_tips


def test_apt():
    assert package_tips("efibootmgr", has_apt=True, has_dnf=False, has_pacman=False) == "sudo apt install efibootmgr"


def test_dnf():
    assert package_tips("efibootmgr", has_apt=False, has_dnf=True, has_pacman=False) == "sudo dnf install efibootmgr"


def test_pacman():
    assert package_tips("efibootmgr", has_apt=False, has_dnf=False, has_pacman=True) == "sudo pacman -S efibootmgr"


def test_none_found():
    assert package_tips("efibootmgr", has_apt=False, has_dnf=False, has_pacman=False) == "Please install efibootmgr"
