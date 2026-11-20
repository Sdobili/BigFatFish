"""Every guard-named test must be listed in guard_tests of the manifest."""

import ast
import re
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_MANIFEST = _ROOT / "tests" / "mutations.toml"
_GUARD_NAME = re.compile(r"rejects|blocked|_exits_[12]$|_is_error$")


def test_guard_named_tests_are_listed() -> None:
    with _MANIFEST.open("rb") as handle:
        listed = set(tomllib.load(handle).get("guard_tests", []))
    named: list[str] = []
    for path in sorted((_ROOT / "tests").rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                if _GUARD_NAME.search(node.name):
                    named.append(f"{path.relative_to(_ROOT).as_posix()}::{node.name}")
    unlisted = [node_id for node_id in named if node_id not in listed]
    assert unlisted == []
