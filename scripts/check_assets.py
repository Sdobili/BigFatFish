"""Reject tracked images that are unregistered or outside the asset dirs.

Scans `git ls-files` only. An ignored file that was never added is invisible.
Images and design sources may live in assets/placeholder/ or assets/own/, and
each one must be listed in ASSETS.md with source 自制 or 程序生成.
A tracked file is also an asset when its first 1024 bytes match _SIGNATURES.
A path listed twice, or listed but not tracked, is a violation.
"""

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TextIO

_ASSET_SUFFIXES = frozenset(
    {
        ".ai",
        ".apng",
        ".avif",
        ".bmp",
        ".clip",
        ".cur",
        ".eps",
        ".gif",
        ".heic",
        ".heif",
        ".ico",
        ".jfif",
        ".jpeg",
        ".jpg",
        ".kra",
        ".m4v",
        ".mkv",
        ".mov",
        ".mp4",
        ".png",
        ".psb",
        ".psd",
        ".svg",
        ".svgz",
        ".tif",
        ".tiff",
        ".webm",
        ".webp",
        ".xcf",
    }
)
_WHITELIST_PREFIXES = ("assets/placeholder/", "assets/own/")
_SOURCES = frozenset({"自制", "程序生成"})


def main() -> int:
    root = _repo_root()
    tracked = _tracked_files(root)
    registry, violations = _load_registry(root / "ASSETS.md")
    tracked_set = set(tracked)
    for path in registry:
        if path not in tracked_set:
            violations.append(f"{path}: 在 ASSETS.md 登记，但不在 git 跟踪的文件里")
    for path in tracked:
        sniffed = _sniff(_read_head(root / path))
        if Path(path).suffix.lower() not in _ASSET_SUFFIXES:
            if sniffed is None:
                continue
            violations.append(f"{path}: 文件头是 {sniffed}，按素材处理")
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
        _write_utf8("\n".join(violations))
        return 1
    _write_utf8("OK")
    return 0


def _write_utf8(text: str, stream: TextIO | None = None) -> None:
    """Write UTF-8 bytes so a cp1252 Windows console does not raise."""
    target = sys.stdout if stream is None else stream
    payload = (text + "\n").encode("utf-8")
    raw = getattr(target, "buffer", None)
    if raw is None:
        target.write(text + "\n")
        return
    raw.write(payload)
    raw.flush()


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
        print(
            f"git ls-files 失败（退出码 {result.returncode}）",
            file=sys.stderr,
        )
        sys.stderr.buffer.write(result.stderr)
        raise SystemExit(result.returncode)
    return [item for item in result.stdout.decode("utf-8").split("\0") if item]


def _load_registry(path: Path) -> tuple[dict[str, str], list[str]]:
    found: dict[str, str] = {}
    first_line: dict[str, int] = {}
    violations: list[str] = []
    if not path.is_file():
        return found, violations
    lines = path.read_text(encoding="utf-8").splitlines()
    for line_no, line in enumerate(lines, start=1):
        row = line.strip()
        if not row.startswith("|"):
            continue
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        if len(cells) < 2:
            continue
        asset_path, source = cells[0], cells[1]
        if asset_path == "路径" or _is_separator(asset_path):
            continue
        if asset_path in first_line:
            earlier = first_line[asset_path]
            violations.append(
                f"{asset_path}: ASSETS.md 重复登记（第 {earlier}、{line_no} 行）"
            )
        else:
            first_line[asset_path] = line_no
        found[asset_path] = source
    return found, violations


def _is_separator(cell: str) -> bool:
    return cell != "" and all(char in "-:" for char in cell)


def _read_head(path: Path) -> bytes:
    if not path.is_file():
        return b""
    with path.open("rb") as handle:
        return handle.read(1024)


def _starts(prefix: bytes) -> Callable[[bytes], bool]:
    def detect(head: bytes) -> bool:
        return head.startswith(prefix)

    return detect


def _starts_any(prefixes: tuple[bytes, ...]) -> Callable[[bytes], bool]:
    def detect(head: bytes) -> bool:
        return head.startswith(prefixes)

    return detect


def _detect_webp(head: bytes) -> bool:
    return head.startswith(b"RIFF") and head[8:12] == b"WEBP"


def _detect_bmp(head: bytes) -> bool:
    if not head.startswith(b"BM") or len(head) < 18:
        return False
    size = int.from_bytes(head[14:18], "little")
    return size in {12, 40, 52, 56, 64, 108, 124}


def _detect_icon(head: bytes, kind: bytes) -> bool:
    if len(head) < 6 or head[:4] != kind:
        return False
    return int.from_bytes(head[4:6], "little") >= 1


def _detect_ico(head: bytes) -> bool:
    return _detect_icon(head, b"\x00\x00\x01\x00")


def _detect_cur(head: bytes) -> bool:
    return _detect_icon(head, b"\x00\x00\x02\x00")


def _detect_bmff(head: bytes) -> bool:
    return len(head) >= 8 and head[4:8] == b"ftyp"


def _detect_quicktime(head: bytes) -> bool:
    return len(head) >= 8 and head[4:8] in {b"moov", b"mdat", b"wide"}


def _detect_kra(head: bytes) -> bool:
    return (
        head.startswith(b"PK\x03\x04")
        and head[30:38] == b"mimetype"
        and head[38:57] == b"application/x-krita"
    )


def _detect_svg(head: bytes) -> bool:
    if b"<svg" not in head.lower():
        return False
    payload = head[3:] if head.startswith(b"\xef\xbb\xbf") else head
    start = payload.lstrip()
    if start.startswith(b"<?xml"):
        return True
    folded = start.lower()
    return folded.startswith((b"<svg", b"<!doctype svg"))


_SIGNATURES: tuple[tuple[str, Callable[[bytes], bool]], ...] = (
    ("PNG", _starts(b"\x89PNG\r\n\x1a\n")),
    ("JPEG", _starts(b"\xff\xd8\xff")),
    ("GIF", _starts_any((b"GIF87a", b"GIF89a"))),
    ("WebP", _detect_webp),
    ("BMP", _detect_bmp),
    ("TIFF", _starts_any((b"II*\x00", b"MM\x00*"))),
    ("ICO", _detect_ico),
    ("CUR", _detect_cur),
    ("ISO BMFF", _detect_bmff),
    ("QuickTime", _detect_quicktime),
    ("Matroska", _starts(b"\x1a\x45\xdf\xa3")),
    ("PSD", _starts(b"8BPS")),
    ("XCF", _starts(b"gimp xcf")),
    ("PDF", _starts(b"%PDF-")),
    ("EPS", _starts_any((b"%!PS-Adobe", b"\xc5\xd0\xd3\xc6"))),
    ("KRA", _detect_kra),
    ("SVG", _detect_svg),
)


def _sniff(head: bytes) -> str | None:
    for name, detect in _SIGNATURES:
        if detect(head):
            return name
    return None


if __name__ == "__main__":
    raise SystemExit(main())
