"""Pytest configuration and fixtures for Scale-Note tests.

Adds the `src/` directory to sys.path so tests can import the modules directly.
Provides common fixtures like simple chord progressions.
"""

import sys
from pathlib import Path
import pytest

# Add src/ to sys.path
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture()
def simple_progression() -> list:
    """Return a simple I-IV-V-I progression in C major."""
    return ["C major", "F major", "G major", "C major"]


@pytest.fixture()
def short_progression() -> list:
    """Short progression for quick tests."""
    return ["C major", "G major"]
