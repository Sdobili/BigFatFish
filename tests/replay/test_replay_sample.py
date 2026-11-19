"""Replay recorded gestures and compare the trace to the golden file."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.replay

_FIXTURE = Path(__file__).parent / "fixtures" / "sample.jsonl"
_GOLDEN = Path(__file__).parent / "golden" / "sample.jsonl"

_CLOCK_GUARD = """\
import time


def _boom(*_args: object, **_kwargs: object) -> float:
    raise RuntimeError("wall clock")


time.time = _boom
time.monotonic = _boom
time.perf_counter = _boom
time.time_ns = _boom
time.monotonic_ns = _boom
"""


def test_replay_sample(tmp_path: Path) -> None:
    from bigfatfish.replay.format import write_jsonl

    from bigfatfish.core.events import GestureEvent, load_event

    events = [
        load_event(json.loads(line))
        for line in _FIXTURE.read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert events
    assert all(isinstance(event, GestureEvent) for event in events)

    recorded = tmp_path / "recorded.jsonl"
    write_jsonl(recorded, events)
    assert recorded.read_bytes() == _FIXTURE.read_bytes()

    out = tmp_path / "trace.jsonl"
    proc = _replay(_FIXTURE, out, poison_clock=False, guard_dir=tmp_path / "guard")
    assert proc.returncode == 0, proc.stderr.decode()
    assert out.read_bytes() == _GOLDEN.read_bytes()

    guarded = tmp_path / "guarded.jsonl"
    poisoned = _replay(
        _FIXTURE,
        guarded,
        poison_clock=True,
        guard_dir=tmp_path / "clock-guard",
    )
    assert poisoned.returncode == 0, poisoned.stderr.decode()
    assert guarded.read_bytes() == _GOLDEN.read_bytes()


def test_replay_altered_fixture_does_not_match_golden(tmp_path: Path) -> None:
    """One fewer event must not reproduce the sample golden trace."""
    body = _FIXTURE.read_text(encoding="utf-8").splitlines(keepends=True)
    altered = tmp_path / "altered.jsonl"
    altered.write_text("".join(body[:-1]), encoding="utf-8")

    out = tmp_path / "trace.jsonl"
    proc = _replay(altered, out, poison_clock=False, guard_dir=tmp_path / "guard")
    assert proc.returncode == 0, proc.stderr.decode()
    assert out.read_bytes() != _GOLDEN.read_bytes()


def _replay(
    fixture: Path,
    out: Path,
    *,
    poison_clock: bool,
    guard_dir: Path,
) -> subprocess.CompletedProcess[bytes]:
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    if poison_clock:
        guard_dir.mkdir(parents=True, exist_ok=True)
        (guard_dir / "sitecustomize.py").write_text(_CLOCK_GUARD, encoding="utf-8")
        previous = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            str(guard_dir) if previous == "" else str(guard_dir) + os.pathsep + previous
        )
    return subprocess.run(
        [sys.executable, "-m", "bigfatfish.replay", str(fixture), "--out", str(out)],
        check=False,
        capture_output=True,
        env=env,
    )
