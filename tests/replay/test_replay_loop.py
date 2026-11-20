"""Replay the closed loop under a poisoned wall clock."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.replay

_FIXTURES = Path(__file__).parent / "fixtures"
_GOLDEN = Path(__file__).parent / "golden"
_MAIN_FIXTURE = _FIXTURES / "loop_main.jsonl"
_MAIN_GOLDEN = _GOLDEN / "loop_main.jsonl"
_REVISE_FIXTURE = _FIXTURES / "loop_revise.jsonl"
_REVISE_GOLDEN = _GOLDEN / "loop_revise.jsonl"

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

_RUNNER = """\
import sys
from pathlib import Path

from bigfatfish.replay.format import load_session
from bigfatfish.replay.play import render_loop_trace

events = load_session(Path(sys.argv[1]))
lines = render_loop_trace(events)
nl = chr(10)
Path(sys.argv[2]).write_text(nl.join(lines) + nl, encoding="utf-8", newline=nl)
"""


def test_loop_main_path(tmp_path: Path) -> None:
    out = tmp_path / "trace.jsonl"
    proc = _replay(tmp_path / "guard", _MAIN_FIXTURE, out)
    detail = proc.stderr.decode() + proc.stdout.decode()
    assert proc.returncode == 0, detail
    assert out.read_bytes() == _MAIN_GOLDEN.read_bytes(), (
        "loop trace differs from golden"
    )
    assert _deliver_count(out) == 1


def test_loop_revise_path(tmp_path: Path) -> None:
    out = tmp_path / "trace.jsonl"
    proc = _replay(tmp_path / "guard", _REVISE_FIXTURE, out)
    detail = proc.stderr.decode() + proc.stdout.decode()
    assert proc.returncode == 0, detail
    assert out.read_bytes() == _REVISE_GOLDEN.read_bytes(), (
        "loop trace differs from golden"
    )
    deliver = _deliver(out)
    assert deliver["box"] == [[0.1, 0.1], [0.9, 0.9]]
    assert deliver["revisions"] == 1


def _deliver_count(path: Path) -> int:
    return len(_delivers(path))


def _deliver(path: Path) -> dict[str, object]:
    found = _delivers(path)
    assert len(found) == 1
    return found[0]


def _delivers(path: Path) -> list[dict[str, object]]:
    last = json.loads(path.read_text(encoding="utf-8").splitlines()[-1])
    effects = last["effects"]
    assert isinstance(effects, list)
    found: list[dict[str, object]] = []
    for item in effects:
        if isinstance(item, dict) and item.get("kind") == "Deliver":
            found.append(item)
    return found


def _replay(
    guard_dir: Path,
    fixture: Path,
    out: Path,
) -> subprocess.CompletedProcess[bytes]:
    guard_dir.mkdir(parents=True, exist_ok=True)
    (guard_dir / "sitecustomize.py").write_text(_CLOCK_GUARD, encoding="utf-8")
    runner = guard_dir / "run_loop_trace.py"
    runner.write_text(_RUNNER, encoding="utf-8")
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    previous = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(guard_dir) if previous == "" else str(guard_dir) + os.pathsep + previous
    )
    return subprocess.run(
        [sys.executable, str(runner), str(fixture), str(out)],
        check=False,
        capture_output=True,
        env=env,
    )
