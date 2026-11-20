"""FakeClock moves only when told, and time is imported in one place."""

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_PACKAGE = _REPO / "src" / "bigfatfish"
_CLOCK = _PACKAGE / "core" / "clock.py"
_TIME_IMPORT = re.compile(r"^\s*(import time\b|from time\b)")


def test_fake_clock_advance_moves_monotonic_and_wall() -> None:
    from bigfatfish.core.clock import FakeClock

    clock = FakeClock(start_monotonic=10.0, start_wall=1_700_000_000.0)
    assert clock.monotonic() == 10.0
    assert clock.wall() == 1_700_000_000.0
    clock.advance(2.5)
    assert clock.monotonic() == 12.5
    assert clock.wall() == 1_700_000_002.5
    clock.advance(0.5)
    assert clock.monotonic() == 13.0
    assert clock.wall() == 1_700_000_003.0


def test_fake_clock_starts_at_zero() -> None:
    from bigfatfish.core.clock import FakeClock

    clock = FakeClock()
    assert clock.monotonic() == 0.0
    assert clock.wall() == 0.0


def test_no_time_import_outside_clock() -> None:
    offenders: list[str] = []
    for path in sorted(_PACKAGE.rglob("*.py")):
        if path.resolve() == _CLOCK.resolve():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        if any(_TIME_IMPORT.search(line) for line in lines):
            offenders.append(path.relative_to(_REPO).as_posix())
    assert offenders == []
