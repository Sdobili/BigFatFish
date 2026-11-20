"""The asset gate looks only at git-tracked images and design files."""

import functools
import importlib.util
import os
import struct
import subprocess
import sys
import zlib
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_assets.py"
_ROOT = Path(__file__).resolve().parents[1]
_SNIFF_CASES: tuple[tuple[bytes, str | None], ...] = (
    (b"\x89PNG\r\n\x1a\n", "PNG"),
    (b"\xff\xd8\xff", "JPEG"),
    (b"GIF87a", "GIF"),
    (b"GIF89a", "GIF"),
    (b"RIFF\x00\x00\x00\x00WEBP", "WebP"),
    (b"BM" + b"\x00" * 12 + struct.pack("<I", 40), "BMP"),
    (b"II*\x00", "TIFF"),
    (b"MM\x00*", "TIFF"),
    (b"\x00\x00\x01\x00" + struct.pack("<H", 1), "ICO"),
    (b"\x00\x00\x02\x00" + struct.pack("<H", 1), "CUR"),
    (b"\x00\x00\x00\x00ftyp", "ISO BMFF"),
    (b"\x00\x00\x00\x00moov", "QuickTime"),
    (b"\x00\x00\x00\x00mdat", "QuickTime"),
    (b"\x00\x00\x00\x00wide", "QuickTime"),
    (b"\x1a\x45\xdf\xa3", "Matroska"),
    (b"8BPS", "PSD"),
    (b"gimp xcf", "XCF"),
    (b"%PDF-", "PDF"),
    (b"%!PS-Adobe", "EPS"),
    (b"\xc5\xd0\xd3\xc6", "EPS"),
    (b"PK\x03\x04" + b"\x00" * 26 + b"mimetypeapplication/x-krita", "KRA"),
    (b"<svg", "SVG"),
    (b"<?xml version='1.0'?><svg", "SVG"),
    (b"<!DOCTYPE svg><svg", "SVG"),
    (b"\xef\xbb\xbf \n<svg", "SVG"),
    (b"<SVG", "SVG"),
    (b"", None),
    (b"hello world\n", None),
    (b"print('hello')\n", None),
    (b"PK\x03\x04" + b"\x00" * 26 + b"readme.txt", None),
    (b"BM hello", None),
    (b"BM" + b"\x00" * 12 + struct.pack("<I", 16) + b" text", None),
    (b"\x00\x00\x01\x00" + struct.pack("<H", 0), None),
    (b"RIFF\x00\x00\x00\x00AVI ", None),
    (b"<?xml version='1.0'?>", None),
    (b"PK\x03\x04" + b"\x00" * 26 + b"mimetypeapplication/zip", None),
)
_ASSET_SUFFIXES = (
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
)


def test_check_assets_rejects_other_source(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    image = repo / "assets" / "placeholder" / "other.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(_png())
    (repo / "ASSETS.md").write_text(
        _registry([("assets/placeholder/other.png", "他人", "not ours")]),
        encoding="utf-8",
    )
    _git(repo, "add", "ASSETS.md", "assets/placeholder/other.png")
    _git(repo, "commit", "-m", "register a third-party source")

    result = _run(repo)
    combined = result.stdout + result.stderr
    assert result.returncode != 0
    assert "来源必须是" in combined
    assert "OK" not in result.stdout.splitlines()


def test_check_assets_rejects_unregistered_image(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    image = repo / "assets" / "placeholder" / "extra.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(_png())
    (repo / "ASSETS.md").write_text(_registry([]), encoding="utf-8")
    _git(repo, "add", "ASSETS.md", "assets/placeholder/extra.png")
    _git(repo, "commit", "-m", "add unregistered image")

    result = _run(repo)
    combined = result.stdout + result.stderr
    assert result.returncode != 0
    assert "assets/placeholder/extra.png" in combined
    assert "未在 ASSETS.md 登记" in combined
    assert "OK" not in result.stdout.splitlines()


def test_check_assets_rejects_image_outside_whitelist(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    image = repo / "notes" / "pic.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(_png())
    (repo / "ASSETS.md").write_text(
        _registry([("notes/pic.png", "自制", "test")]),
        encoding="utf-8",
    )
    _git(repo, "add", "ASSETS.md", "notes/pic.png")
    _git(repo, "commit", "-m", "add image outside the asset dirs")

    result = _run(repo)
    combined = result.stdout + result.stderr
    assert result.returncode != 0
    assert "notes/pic.png" in combined
    assert "assets/placeholder/" in combined
    assert "assets/own/" in combined
    assert "OK" not in result.stdout.splitlines()


def test_check_assets_rejects_force_tracked_local(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / ".gitignore").write_text("assets/local/\n", encoding="utf-8")
    image = repo / "assets" / "local" / "x.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(_png())
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-m", "ignore local assets")
    _git(repo, "add", "-f", "--", "assets/local/x.png")
    _git(repo, "commit", "-m", "force track a local image")
    tracked = _git(repo, "ls-files", "--", "assets/local/x.png")
    assert tracked.stdout.strip() == "assets/local/x.png"

    result = _run(repo)
    combined = result.stdout + result.stderr
    assert result.returncode != 0
    assert "assets/local/x.png" in combined
    assert "OK" not in result.stdout.splitlines()


@pytest.mark.parametrize("suffix", [".PNG", ".CLIP"])
def test_check_assets_rejects_uppercase_extension(tmp_path: Path, suffix: str) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    relative = f"assets/placeholder/sample{suffix}"
    image = repo / relative
    image.parent.mkdir(parents=True)
    image.write_bytes(b"not-a-magic-header\n")
    (repo / "ASSETS.md").write_text(_registry([]), encoding="utf-8")
    _git(repo, "add", "ASSETS.md", relative)
    _git(repo, "commit", "-m", "add an uppercase asset")

    result = _run(repo)
    combined = result.stdout + result.stderr
    assert result.returncode != 0
    assert relative in combined
    assert "未在 ASSETS.md 登记" in combined
    assert "OK" not in result.stdout.splitlines()


def test_check_assets_rejects_when_ls_files_fails(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "README").write_text("ok\n", encoding="utf-8")
    _git(repo, "add", "README")
    _git(repo, "commit", "-m", "init")
    bad_index = repo / "bad-index"
    bad_index.write_bytes(b"not-an-index")

    result = _run(repo, extra_env={"GIT_INDEX_FILE": str(bad_index)})
    assert result.returncode != 0
    assert f"git ls-files 失败（退出码 {result.returncode}）" in result.stderr
    assert "OK" not in result.stdout.splitlines()


def test_check_assets_accepts_registered_assets(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    placeholder = repo / "assets" / "placeholder" / "ok.png"
    own = repo / "assets" / "own" / "mine.png"
    placeholder.parent.mkdir(parents=True)
    own.parent.mkdir(parents=True)
    placeholder.write_bytes(_png())
    own.write_bytes(_png())
    (repo / "ASSETS.md").write_text(
        _registry(
            [
                ("assets/placeholder/ok.png", "程序生成", "script"),
                ("assets/own/mine.png", "自制", "drawn for this repo"),
            ]
        ),
        encoding="utf-8",
    )
    _git(
        repo,
        "add",
        "ASSETS.md",
        "assets/placeholder/ok.png",
        "assets/own/mine.png",
    )
    _git(repo, "commit", "-m", "add registered assets")

    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines() == ["OK"]


def test_check_assets_ignores_untracked_gitignored_local(tmp_path: Path) -> None:
    """An ignored, untracked assets/local image is outside the gate."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / ".gitignore").write_text("assets/local/\n", encoding="utf-8")
    image = repo / "assets" / "local" / "x.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(_png())
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-m", "ignore local assets")
    tracked = _git(repo, "ls-files")
    assert "assets/local/x.png" not in tracked.stdout.splitlines()
    ignored = subprocess.run(
        ["git", "check-ignore", "assets/local/x.png"],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    assert ignored.returncode == 0

    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines() == ["OK"]


def test_check_assets_rejects_png_renamed_to_bin(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    image = repo / "notes" / "pic.bin"
    image.parent.mkdir(parents=True)
    image.write_bytes(_png())
    (repo / "ASSETS.md").write_text(_registry([]), encoding="utf-8")
    _git(repo, "add", "ASSETS.md", "notes/pic.bin")
    _git(repo, "commit", "-m", "add a png renamed to bin")

    result = _run(repo)
    combined = result.stdout + result.stderr
    assert "notes/pic.bin: 文件头是 PNG" in combined
    assert "notes/pic.bin: 图片必须放在 assets/placeholder/ 或 assets/own/" in combined
    assert "notes/pic.bin: 未在 ASSETS.md 登记" in combined
    assert result.returncode != 0
    assert "OK" not in result.stdout.splitlines()


def test_check_assets_rejects_signature_at_end_of_head(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    image = repo / "notes" / "late.bin"
    image.parent.mkdir(parents=True)
    image.write_bytes(b" " * 1020 + b"<svg")
    (repo / "ASSETS.md").write_text(_registry([]), encoding="utf-8")
    _git(repo, "add", "ASSETS.md", "notes/late.bin")
    _git(repo, "commit", "-m", "add an svg signature at the end of the head")

    result = _run(repo)
    combined = result.stdout + result.stderr
    assert result.returncode != 0
    assert "notes/late.bin: 文件头是 SVG" in combined
    assert "notes/late.bin: 图片必须放在 assets/placeholder/ 或 assets/own/" in combined
    assert "notes/late.bin: 未在 ASSETS.md 登记" in combined
    assert "OK" not in result.stdout.splitlines()


@pytest.mark.parametrize("suffix", _ASSET_SUFFIXES)
def test_check_assets_rejects_new_extensions(tmp_path: Path, suffix: str) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    relative = f"assets/placeholder/sample{suffix}"
    image = repo / relative
    image.parent.mkdir(parents=True)
    image.write_bytes(b"not-a-magic-header\n")
    (repo / "ASSETS.md").write_text(_registry([]), encoding="utf-8")
    _git(repo, "add", "ASSETS.md", relative)
    _git(repo, "commit", "-m", "add an unregistered asset")

    result = _run(repo)
    combined = result.stdout + result.stderr
    assert result.returncode != 0
    assert f"{relative}: 未在 ASSETS.md 登记" in combined
    assert "OK" not in result.stdout.splitlines()


@pytest.mark.parametrize("sources", [("他人", "自制"), ("自制", "他人")])
def test_check_assets_rejects_duplicate_registration(
    tmp_path: Path, sources: tuple[str, str]
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    image = repo / "assets" / "own" / "x.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(_png())
    first, second = sources
    (repo / "ASSETS.md").write_text(
        _registry(
            [
                ("assets/own/x.png", first, "first"),
                ("assets/own/x.png", second, "second"),
            ]
        ),
        encoding="utf-8",
    )
    _git(repo, "add", "ASSETS.md", "assets/own/x.png")
    _git(repo, "commit", "-m", "register one path twice")

    result = _run(repo)
    combined = result.stdout + result.stderr
    assert "assets/own/x.png: ASSETS.md 重复登记（第 5、6 行）" in combined
    assert result.returncode != 0
    assert "OK" not in result.stdout.splitlines()


def test_check_assets_rejects_registered_but_missing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "ASSETS.md").write_text(
        _registry([("assets/own/gone.png", "自制", "not in the tree")]),
        encoding="utf-8",
    )
    _git(repo, "add", "ASSETS.md")
    _git(repo, "commit", "-m", "register a missing file")

    result = _run(repo)
    combined = result.stdout + result.stderr
    assert "assets/own/gone.png: 在 ASSETS.md 登记，但不在 git 跟踪的文件里" in combined
    assert result.returncode != 0
    assert "OK" not in result.stdout.splitlines()


@pytest.mark.parametrize(("head", "expected"), _SNIFF_CASES)
def test_sniff_signatures(head: bytes, expected: str | None) -> None:
    assert _sniff(head) == expected


def test_repo_gitignore_covers_assets_local() -> None:
    gitignore = (_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "assets/local/" in gitignore.splitlines()
    result = subprocess.run(
        ["git", "check-ignore", "assets/local/x.png"],
        cwd=_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "assets/local/x.png"


@functools.cache
def _check_assets() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_assets", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sniff(head: bytes) -> str | None:
    sniffed = _check_assets()._sniff(head)
    assert sniffed is None or isinstance(sniffed, str)
    return sniffed


def _run(
    repo: Path,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("PYTHONUTF8", None)
    env.pop("PYTHONIOENCODING", None)
    if extra_env is not None:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(_SCRIPT)],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "asset-test")


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result


def _registry(rows: list[tuple[str, str, str]]) -> str:
    lines = [
        "# 素材登记",
        "",
        "| 路径 | 来源 | 说明 |",
        "| --- | --- | --- |",
    ]
    lines.extend(f"| {path} | {source} | {note} |" for path, source, note in rows)
    lines.append("")
    return "\n".join(lines)


def _png() -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    raw = b"\x00" + bytes((255, 0, 0, 255))
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
