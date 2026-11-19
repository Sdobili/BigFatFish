"""The asset gate looks only at git-tracked images and design files."""

import os
import struct
import subprocess
import sys
import zlib
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_assets.py"
_ROOT = Path(__file__).resolve().parents[1]


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


def _run(repo: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("PYTHONUTF8", None)
    env.pop("PYTHONIOENCODING", None)
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
