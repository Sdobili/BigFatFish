"""Reject tracked images that are unregistered or outside the asset dirs.

Scans `git ls-files` only. An ignored file that was never added is invisible.
Images and design sources may live in assets/placeholder/ or assets/own/, and
each one must be listed in ASSETS.md with source 自制 or 程序生成.
"""

import subprocess
import sys
from pathlib import Path

_ASSET_SUFFIXES = frozenset(
    {
        ".bmp",
        ".clip",
        ".gif",
        ".jpeg",
        ".jpg",
        ".kra",
        ".mp4",
        ".png",
        ".psd",
        ".svg",
        ".webm",
        ".webp",
    }
)
_WHITELIST_PREFIXES = ("assets/placeholder/", "assets/own/")
_SOURCES = frozenset({"自制", "程序生成"})


def main() -> int:
    root = _repo_root()
    registry = _load_registry(root / "ASSETS.md")
    violations: list[str] = []
    for path in _tracked_files(root):
        if Path(path).suffix.lower() not in _ASSET_SUFFIXES:
            continue
        if not path.startswith(_WHITELIST_PREFIXES):
            violations.append(
                f"{path}: 图片必须放在 assets/placeholder/ 或 assets/own/"
            )
        source = registry.get(path)
        if source is None:
            violations.append(f"{path}: 未在 ASSETS.md 登记")
        elif source not in _SOURCES:
            violations.append(f"{path}: 来源必须是「自制」或「程序生成」")
    if violations:
        print("\n".join(violations))
        return 1
    return 0


def _repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode)
    return Path(result.stdout.strip())


def _tracked_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        sys.stderr.buffer.write(result.stderr)
        raise SystemExit(result.returncode)
    return [item for item in result.stdout.decode("utf-8").split("\0") if item]


def _load_registry(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    found: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        row = line.strip()
        if not row.startswith("|"):
            continue
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        if len(cells) < 2:
            continue
        asset_path, source = cells[0], cells[1]
        if asset_path == "路径" or _is_separator(asset_path):
            continue
        found[asset_path] = source
    return found


def _is_separator(cell: str) -> bool:
    return cell != "" and all(char in "-:" for char in cell)


if __name__ == "__main__":
    raise SystemExit(main())
