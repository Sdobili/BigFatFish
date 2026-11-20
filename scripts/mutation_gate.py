"""Patch each manifest mutant, require the expected failure, then restore."""

import argparse
import hashlib
import os
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_TAIL_LINES = 20


@dataclass(frozen=True)
class Mutant:
    id: str
    file: str
    original: str
    replacement: str
    kill: tuple[str, ...]
    expect: str
    why: str


@dataclass(frozen=True)
class Args:
    manifest: str
    root: str
    only: tuple[str, ...] | None
    hang_guard: float


def main(argv: list[str] | None = None) -> int:
    parsed = _parse_args(sys.argv[1:] if argv is None else argv)
    if isinstance(parsed, str):
        print(parsed)
        return 2
    root = Path(parsed.root)
    manifest = Path(parsed.manifest)
    if not manifest.is_absolute():
        manifest = root / manifest
    loaded = _load_manifest(manifest)
    if isinstance(loaded, str):
        print(loaded)
        return 2
    mutants = loaded
    if parsed.only is not None:
        selected = _select(mutants, parsed.only)
        if isinstance(selected, str):
            print(selected)
            return 2
        mutants = selected
    problem = _validate_snippets(root, mutants)
    if problem is not None:
        print(problem)
        return 2
    if _baseline_failed(root, mutants, parsed.hang_guard):
        return 2
    return _run_mutants(root, mutants, parsed.hang_guard)


def _parse_args(argv: list[str]) -> Args | str:
    parser = argparse.ArgumentParser(prog="mutation_gate")
    parser.add_argument("manifest", nargs="?", default="tests/mutations.toml")
    parser.add_argument("--root", default=".")
    parser.add_argument("--only", nargs="+")
    parser.add_argument("--hang-guard", type=float, default=120.0)
    parsed = parser.parse_args(argv)
    manifest = parsed.manifest
    root = parsed.root
    hang_guard = parsed.hang_guard
    only = parsed.only
    if not isinstance(manifest, str) or not isinstance(root, str):
        return "invalid arguments"
    if not isinstance(hang_guard, float):
        return "invalid hang guard"
    if only is None:
        return Args(manifest, root, None, hang_guard)
    if not isinstance(only, list):
        return "invalid --only"
    only_ids: list[str] = []
    for item in only:
        if not isinstance(item, str):
            return "invalid --only"
        only_ids.append(item)
    return Args(manifest, root, tuple(only_ids), hang_guard)


def _load_manifest(path: Path) -> list[Mutant] | str:
    if not path.is_file():
        return f"manifest not found: {path}"
    try:
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        return f"invalid manifest: {exc}"
    entries = raw.get("mutant")
    if not isinstance(entries, list):
        return "manifest has no [[mutant]] entries"
    mutants: list[Mutant] = []
    seen: set[str] = set()
    for entry in entries:
        parsed = _parse_mutant(entry)
        if isinstance(parsed, str):
            return parsed
        if parsed.id in seen:
            return f"duplicate mutant id: {parsed.id}"
        seen.add(parsed.id)
        mutants.append(parsed)
    problem = _check_manifest(raw, mutants)
    if problem is not None:
        return problem
    return mutants


def _check_manifest(raw: dict[str, Any], mutants: list[Mutant]) -> str | None:
    if not mutants:
        return "manifest has no mutants"
    required_ids = _required_id_list(raw.get("required_ids"))
    if required_ids is None:
        return "manifest has no required_ids list"
    known = {mutant.id for mutant in mutants}
    missing = [mutant_id for mutant_id in required_ids if mutant_id not in known]
    if missing:
        return f"required mutant missing: {missing[0]}"
    required = set(required_ids)
    for mutant in mutants:
        if mutant.id not in required:
            return f"mutant not in required_ids: {mutant.id}"
    guards = raw.get("guard_tests", [])
    if not isinstance(guards, list):
        return "guard_tests is not a list"
    owned = {mutant.kill[0] for mutant in mutants if len(mutant.kill) == 1}
    for guard in guards:
        if guard not in owned:
            return f"guard test has no own mutant: {guard}"
    return None


def _required_id_list(value: object) -> list[str] | None:
    if not isinstance(value, list) or len(value) == 0:
        return None
    ids: list[str] = []
    for item in value:
        if not isinstance(item, str) or item == "":
            return None
        ids.append(item)
    return ids


def _parse_mutant(entry: object) -> Mutant | str:
    if not isinstance(entry, dict):
        return "mutant entry is not a table"
    raw_id = entry.get("id")
    label = raw_id if isinstance(raw_id, str) and raw_id else "<unknown>"
    file_name = _required_str(entry, "file", allow_empty=False)
    original = _required_str(entry, "original", allow_empty=False)
    replacement = _required_str(entry, "replacement", allow_empty=True)
    expect = _required_str(entry, "expect", allow_empty=False)
    why = _required_str(entry, "why", allow_empty=False)
    kill = _required_kill(entry)
    if (
        not isinstance(raw_id, str)
        or raw_id == ""
        or file_name is None
        or original is None
        or replacement is None
        or expect is None
        or why is None
        or kill is None
    ):
        return f"{label}: mutant is missing a required field"
    return Mutant(
        id=raw_id,
        file=file_name,
        original=original,
        replacement=replacement,
        kill=kill,
        expect=expect,
        why=why,
    )


def _required_str(
    entry: dict[Any, Any],
    key: str,
    *,
    allow_empty: bool,
) -> str | None:
    value = entry.get(key)
    if isinstance(value, str) and (allow_empty or value != ""):
        return value
    return None


def _required_kill(entry: dict[Any, Any]) -> tuple[str, ...] | None:
    value = entry.get("kill")
    if not isinstance(value, list) or len(value) == 0:
        return None
    nodes: list[str] = []
    for item in value:
        if not isinstance(item, str) or item == "":
            return None
        nodes.append(item)
    return tuple(nodes)


def _select(mutants: list[Mutant], only: tuple[str, ...]) -> list[Mutant] | str:
    known = {mutant.id for mutant in mutants}
    missing = [mutant_id for mutant_id in only if mutant_id not in known]
    if missing:
        return "unknown mutant id: " + ", ".join(missing)
    wanted = set(only)
    return [mutant for mutant in mutants if mutant.id in wanted]


def _validate_snippets(root: Path, mutants: list[Mutant]) -> str | None:
    for mutant in mutants:
        path = root / mutant.file
        if not path.is_file():
            return f"{mutant.id}: file not found: {mutant.file}"
        count = path.read_bytes().count(mutant.original.encode("utf-8"))
        if count == 1:
            continue
        if count == 0:
            return f"{mutant.id}: original snippet not found in {mutant.file}"
        return f"{mutant.id}: original snippet appears {count} times in {mutant.file}"
    return None


def _baseline_failed(root: Path, mutants: list[Mutant], hang_guard: float) -> bool:
    nodes: list[str] = []
    seen: set[str] = set()
    for mutant in mutants:
        for node in mutant.kill:
            if node not in seen:
                seen.add(node)
                nodes.append(node)
    code, output = _pytest(root, nodes, hang_guard)
    if code == 0:
        return False
    shown = "timeout" if code is None else str(code)
    print(f"baseline failed (pytest exit {shown})")
    _print_tail(output)
    return True


def _run_mutants(root: Path, mutants: list[Mutant], hang_guard: float) -> int:
    killed = 0
    survived = 0
    wrong = 0
    errors = 0
    for mutant in mutants:
        outcome = _one_mutant(root, mutant, hang_guard)
        if outcome == "killed":
            killed += 1
        elif outcome == "survived":
            survived += 1
        elif outcome == "wrong":
            wrong += 1
        else:
            errors += 1
    print(
        "mutation gate: "
        f"{killed} killed, {survived} survived, {wrong} wrong reason, {errors} errors"
    )
    if errors:
        return 2
    if survived or wrong:
        return 1
    return 0


def _one_mutant(root: Path, mutant: Mutant, hang_guard: float) -> str:
    path = root / mutant.file
    original = path.read_bytes()
    patched = original.replace(
        mutant.original.encode("utf-8"),
        mutant.replacement.encode("utf-8"),
        1,
    )
    path.write_bytes(patched)
    outcome = "error"
    try:
        code, output = _pytest(root, list(mutant.kill), hang_guard)
        outcome = _judge(mutant, code, output)
    finally:
        path.write_bytes(original)
        restored = hashlib.sha256(path.read_bytes()).digest()
        if restored != hashlib.sha256(original).digest():
            print(f"ERROR {mutant.id}: restore sha256 mismatch")
            outcome = "error"
    return outcome


def _judge(mutant: Mutant, code: int | None, output: str) -> str:
    if code is None:
        print(f"ERROR {mutant.id}: exceeded hang guard")
        return "error"
    if code == 1 and mutant.expect in output:
        print(f"KILLED {mutant.id}")
        return "killed"
    if code == 0:
        print(f"SURVIVED {mutant.id}")
        _print_tail(output)
        return "survived"
    if code == 1:
        print(f"WRONG_REASON {mutant.id}")
        _print_tail(output)
        return "wrong"
    print(f"ERROR {mutant.id}: pytest exited {code}")
    return "error"


def _print_tail(output: str) -> None:
    for line in output.splitlines()[-_TAIL_LINES:]:
        print(line)


def _pytest(
    root: Path, node_ids: list[str], hang_guard: float
) -> tuple[int | None, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # A same-length write in the same second must not reuse the baseline .pyc.
    with tempfile.TemporaryDirectory(prefix="mutation-pyc-") as cache:
        env["PYTHONPYCACHEPREFIX"] = cache
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                *node_ids,
            ],
            cwd=root,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        try:
            raw, _ = proc.communicate(timeout=hang_guard)
        except subprocess.TimeoutExpired:
            proc.kill()
            raw, _ = proc.communicate()
            return None, _decode(raw)
    code = proc.returncode
    if code is None:
        return None, _decode(raw)
    return code, _decode(raw)


def _decode(raw: bytes | None) -> str:
    if raw is None:
        return ""
    return raw.decode("utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
