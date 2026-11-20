"""Runner tests for the mutation gate.

Each test builds a one-module project under tmp_path and runs
``scripts/mutation_gate.py --root <tmp>``.
"""

import hashlib
import json
import re
import subprocess
import sys
import textwrap
import tomllib
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "mutation_gate.py"
_HANG_GUARD = "30"


def _src(text: str) -> str:
    return textwrap.dedent(text).lstrip("\n")


_VALUE_SOURCE = _src(
    """
    def value() -> int:
        return 1
    """
)
_VALUE_PASSES = _src(
    """
    from sample import value


    def test_value() -> None:
        assert value() == 1
    """
)
_VALUE_FAILS = _src(
    """
    from sample import value


    def test_value() -> None:
        assert value() == 0
    """
)
_TWO_RETURNS = _src(
    """
    def value() -> int:
        return 1


    def other() -> int:
        return 1
    """
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _toml_str(value: str) -> str:
    return json.dumps(value)


def _mutant(
    *,
    mutant_id: str,
    original: str,
    replacement: str,
    kill: str,
    expect: str,
    filename: str = "sample.py",
) -> str:
    return (
        "[[mutant]]\n"
        f"id = {_toml_str(mutant_id)}\n"
        f"file = {_toml_str(filename)}\n"
        f"original = {_toml_str(original)}\n"
        f"replacement = {_toml_str(replacement)}\n"
        f"kill = [{_toml_str(kill)}]\n"
        f"expect = {_toml_str(expect)}\n"
        'why = "unit"\n'
    )


def _with_required_ids(manifest: str) -> str:
    if re.search(r"(?m)^required_ids\s*=", manifest):
        return manifest
    try:
        parsed = tomllib.loads(manifest)
    except tomllib.TOMLDecodeError:
        return manifest
    entries = parsed.get("mutant")
    ids: list[str] = []
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            mutant_id = entry.get("id")
            if isinstance(mutant_id, str):
                ids.append(mutant_id)
    rendered = ", ".join(json.dumps(mutant_id) for mutant_id in ids)
    return f"required_ids = [{rendered}]\n\n{manifest}"


def _project(
    tmp_path: Path,
    source: str,
    test: str,
    manifest: str,
    *,
    fill_required_ids: bool = True,
) -> Path:
    source_path = tmp_path / "sample.py"
    _write(source_path, source)
    _write(tmp_path / "tests" / "test_sample.py", test)
    if fill_required_ids:
        manifest = _with_required_ids(manifest)
    _write(tmp_path / "tests" / "mutations.toml", manifest)
    return source_path


def _run(
    tmp_path: Path, *extra: str, timeout: float | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), "--root", str(tmp_path), *extra],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _summary(stdout: str) -> str:
    lines = stdout.splitlines()
    assert lines
    return lines[-1]


def test_missing_snippet_exits_2(tmp_path: Path) -> None:
    source = _project(
        tmp_path,
        _VALUE_SOURCE,
        _VALUE_PASSES,
        _mutant(
            mutant_id="missing-one",
            original="return 999",
            replacement="return 1",
            kill="tests/test_sample.py::test_value",
            expect="missing",
        ),
    )
    before = source.read_bytes()
    result = _run(tmp_path)
    assert result.returncode == 2
    assert "missing-one" in result.stdout
    assert "sample.py" in result.stdout
    assert source.read_bytes() == before


def test_ambiguous_snippet_exits_2(tmp_path: Path) -> None:
    source = _project(
        tmp_path,
        _TWO_RETURNS,
        _VALUE_PASSES,
        _mutant(
            mutant_id="twice",
            original="return 1",
            replacement="return 2",
            kill="tests/test_sample.py::test_value",
            expect="assert 2 == 1",
        ),
    )
    before = source.read_bytes()
    result = _run(tmp_path)
    assert result.returncode == 2
    assert source.read_bytes() == before


def test_survivor_exits_1(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _VALUE_SOURCE,
        _src(
            """
            def test_value() -> None:
                assert True
            """
        ),
        _mutant(
            mutant_id="lives",
            original="return 1",
            replacement="return 2",
            kill="tests/test_sample.py::test_value",
            expect="assert 2 == 1",
        ),
    )
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "SURVIVED lives" in result.stdout
    assert _summary(result.stdout) == (
        "mutation gate: 0 killed, 1 survived, 0 wrong reason, 0 errors"
    )


def test_all_killed_exits_0(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _VALUE_SOURCE,
        _VALUE_PASSES,
        _mutant(
            mutant_id="dies",
            original="return 1",
            replacement="return 2",
            kill="tests/test_sample.py::test_value",
            expect="assert 2 == 1",
        ),
    )
    result = _run(tmp_path)
    assert result.returncode == 0
    assert "KILLED dies" in result.stdout
    assert _summary(result.stdout) == (
        "mutation gate: 1 killed, 0 survived, 0 wrong reason, 0 errors"
    )


def test_wrong_reason_exits_1(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _VALUE_SOURCE,
        _VALUE_PASSES,
        _mutant(
            mutant_id="wrong",
            original="return 1",
            replacement="return 2",
            kill="tests/test_sample.py::test_value",
            expect="MISSING_REASON",
        ),
    )
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "WRONG_REASON wrong" in result.stdout
    assert _summary(result.stdout) == (
        "mutation gate: 0 killed, 0 survived, 1 wrong reason, 0 errors"
    )


def test_bad_test_id_exits_2(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _VALUE_SOURCE,
        _VALUE_PASSES,
        _mutant(
            mutant_id="missing-test",
            original="return 1",
            replacement="return 2",
            kill="tests/test_sample.py::test_does_not_exist",
            expect="assert 2 == 1",
        ),
    )
    result = _run(tmp_path)
    assert result.returncode == 2
    assert "baseline failed" in result.stdout
    assert "ERROR missing-test" not in result.stdout


def test_failing_baseline_exits_2(tmp_path: Path) -> None:
    source = _project(
        tmp_path,
        _VALUE_SOURCE,
        _VALUE_FAILS,
        _mutant(
            mutant_id="would-pass",
            original="return 1",
            replacement="return 0",
            kill="tests/test_sample.py::test_value",
            expect="assert 0 == 0",
        ),
    )
    before = source.read_bytes()
    result = _run(tmp_path)
    assert result.returncode == 2
    assert "KILLED" not in result.stdout
    assert "SURVIVED" not in result.stdout
    assert "WRONG_REASON" not in result.stdout
    assert source.read_bytes() == before


def test_file_restored_after_each_mutant(tmp_path: Path) -> None:
    source = _project(
        tmp_path,
        _src(
            """
            import time


            def kept() -> int:
                return 10


            def killed() -> int:
                return 20


            def hang() -> int:
                if False:
                    time.sleep(120)
                return 30
            """
        ),
        _src(
            """
            def test_kept() -> None:
                assert True


            def test_killed() -> None:
                from sample import killed

                assert killed() == 20


            def test_hang() -> None:
                from sample import hang

                assert hang() == 30
            """
        ),
        "\n".join(
            (
                _mutant(
                    mutant_id="survives",
                    original="return 10",
                    replacement="return 11",
                    kill="tests/test_sample.py::test_kept",
                    expect="not-checked",
                ),
                _mutant(
                    mutant_id="dies",
                    original="return 20",
                    replacement="return 21",
                    kill="tests/test_sample.py::test_killed",
                    expect="assert 21 == 20",
                ),
                _mutant(
                    mutant_id="hangs",
                    original="if False:",
                    replacement="if True:",
                    kill="tests/test_sample.py::test_hang",
                    expect="not-checked",
                ),
            )
        ),
    )
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    result = _run(tmp_path, "--hang-guard", _HANG_GUARD)
    assert result.returncode == 2
    assert "SURVIVED survives" in result.stdout
    assert "KILLED dies" in result.stdout
    assert "ERROR hangs:" in result.stdout
    assert _summary(result.stdout) == (
        "mutation gate: 1 killed, 1 survived, 0 wrong reason, 1 errors"
    )
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_same_length_mutant_not_masked_by_pyc(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _src(
            """
            def check(n: int) -> bool:
                return n < 1
            """
        ),
        _src(
            """
            from sample import check


            def test_check() -> None:
                assert check(0) is True
            """
        ),
        _mutant(
            mutant_id="bound",
            original="< 1",
            replacement="< 0",
            kill="tests/test_sample.py::test_check",
            expect="assert False is True",
        ),
    )
    result = _run(tmp_path)
    assert result.returncode == 0
    assert "KILLED bound" in result.stdout
    assert _summary(result.stdout) == (
        "mutation gate: 1 killed, 0 survived, 0 wrong reason, 0 errors"
    )


def test_mutant_breaking_import_is_error(tmp_path: Path) -> None:
    source = _project(
        tmp_path,
        _VALUE_SOURCE,
        _VALUE_PASSES,
        _mutant(
            mutant_id="breaks-import",
            original="return 1",
            replacement="return (",
            kill="tests/test_sample.py::test_value",
            expect="SyntaxError",
        ),
    )
    before = source.read_bytes()
    result = _run(tmp_path)
    assert "ERROR breaks-import" in result.stdout
    assert result.returncode == 2
    assert "KILLED" not in result.stdout
    assert source.read_bytes() == before


def test_empty_manifest_exits_2(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _VALUE_SOURCE,
        _VALUE_PASSES,
        "required_ids = []\nmutant = []\n",
    )
    result = _run(tmp_path)
    assert result.returncode == 2
    assert "manifest has no mutants" in result.stdout


def test_missing_required_id_exits_2(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _VALUE_SOURCE,
        _VALUE_PASSES,
        'required_ids = ["dies", "gone"]\n\n'
        + _mutant(
            mutant_id="dies",
            original="return 1",
            replacement="return 2",
            kill="tests/test_sample.py::test_value",
            expect="assert 2 == 1",
        ),
    )
    result = _run(tmp_path)
    assert result.returncode == 2
    assert "required mutant missing: gone" in result.stdout
    assert "KILLED" not in result.stdout


def test_manifest_without_required_ids_exits_2(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _VALUE_SOURCE,
        _VALUE_PASSES,
        _mutant(
            mutant_id="dies",
            original="return 1",
            replacement="return 2",
            kill="tests/test_sample.py::test_value",
            expect="assert 2 == 1",
        ),
        fill_required_ids=False,
    )
    result = _run(tmp_path)
    assert result.returncode == 2
    assert "manifest has no required_ids list" in result.stdout
    assert "KILLED" not in result.stdout


def test_mutant_not_in_required_ids_exits_2(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _src(
            """
            def value() -> int:
                return 1


            def extra() -> int:
                return 3
            """
        ),
        _VALUE_PASSES,
        'required_ids = ["dies"]\n\n'
        + _mutant(
            mutant_id="dies",
            original="return 1",
            replacement="return 2",
            kill="tests/test_sample.py::test_value",
            expect="assert 2 == 1",
        )
        + "\n"
        + _mutant(
            mutant_id="extra",
            original="return 3",
            replacement="return 4",
            kill="tests/test_sample.py::test_value",
            expect="assert 4 == 3",
        ),
    )
    result = _run(tmp_path)
    assert result.returncode == 2
    assert "mutant not in required_ids: extra" in result.stdout
    assert "KILLED" not in result.stdout


def test_guard_test_without_own_mutant_exits_2(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _VALUE_SOURCE,
        _src(
            """
            from sample import value


            def test_value() -> None:
                assert value() == 1


            def test_other() -> None:
                assert value() == 1
            """
        ),
        'guard_tests = ["tests/test_sample.py::test_value"]\n\n'
        + _mutant(
            mutant_id="shared",
            original="return 1",
            replacement="return 2",
            kill="tests/test_sample.py::test_value",
            expect="assert 2 == 1",
        ).replace(
            'kill = ["tests/test_sample.py::test_value"]',
            'kill = ["tests/test_sample.py::test_value", '
            '"tests/test_sample.py::test_other"]',
        ),
    )
    result = _run(tmp_path)
    assert result.returncode == 2
    assert (
        "guard test has no own mutant: tests/test_sample.py::test_value"
        in result.stdout
    )
    assert "KILLED" not in result.stdout


def test_baseline_uses_baseline_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A cold pytest child, with bytecode writes off and a fresh cache prefix,
    # takes longer than 1s (Windows CI reported about 0.8s inside pytest, and
    # the process is slower than that). A 1s hang guard would time out the
    # patched run too. 8s is above that startup and below the 10s sleep.
    # The first red run used 20s/30s and the Windows job then hit its 10 minute
    # limit during the gate.
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    _project(
        tmp_path,
        _src(
            """
            import time


            def value() -> int:
                time.sleep(10)
                return 1
            """
        ),
        _src(
            """
            from sample import value


            def test_value() -> None:
                assert value() == 1
            """
        ),
        _mutant(
            mutant_id="slow-baseline",
            original="time.sleep(10)\n    return 1",
            replacement="return 0",
            kill="tests/test_sample.py::test_value",
            expect="assert 0 == 1",
        ),
    )
    result = _run(tmp_path, "--hang-guard", "8", "--baseline-guard", "60")
    assert result.returncode == 0
    assert "KILLED" in result.stdout


def test_baseline_hang_exits_2(tmp_path: Path) -> None:
    source = _project(
        tmp_path,
        _src(
            """
            import time


            def value() -> int:
                time.sleep(5)
                return 1
            """
        ),
        _src(
            """
            from sample import value


            def test_value() -> None:
                assert value() == 1
            """
        ),
        _mutant(
            mutant_id="hangs-baseline",
            original="time.sleep(5)",
            replacement="return 0",
            kill="tests/test_sample.py::test_value",
            expect="assert 0 == 1",
        ),
    )
    before = source.read_bytes()
    timeout_message = "baseline failed (pytest exit " + "timeout)"
    result = _run(tmp_path, "--baseline-guard", "2", timeout=60)
    assert timeout_message in result.stdout
    assert result.returncode == 2
    assert "KILLED" not in result.stdout
    assert source.read_bytes() == before


def test_gate_sets_hypothesis_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("BIGFATFISH_HYPOTHESIS_PROFILE", raising=False)
    _project(
        tmp_path,
        _src(
            """
            def marker() -> str:
                return "on"
            """
        ),
        _src(
            """
            import os

            from sample import marker


            def test_value() -> None:
                assert os.environ.get("BIGFATFISH_HYPOTHESIS_PROFILE") == "gate"
                assert marker() == "on"
            """
        ),
        _mutant(
            mutant_id="profile-marker",
            original='return "on"',
            replacement='return "off"',
            kill="tests/test_sample.py::test_value",
            expect="assert 'off' == 'on'",
        ),
    )
    result = _run(tmp_path)
    assert result.returncode == 0
    assert "KILLED" in result.stdout
