import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DATA_DIR = Path(__file__).resolve().parent / "test-data"


@pytest.fixture
def efibootmgr_verbose() -> str:
    return (DATA_DIR / "efibootmgr-verbose.txt").read_text(encoding="utf-8")


@pytest.fixture
def efibootmgr_plain() -> str:
    return (DATA_DIR / "efibootmgr.txt").read_text(encoding="utf-8")
