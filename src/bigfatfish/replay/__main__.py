"""Replay a JSONL fixture into a state trace.

Usage: python -m bigfatfish.replay fixture.jsonl --out trace.jsonl
"""

import argparse
from pathlib import Path

from bigfatfish.replay.format import load_jsonl
from bigfatfish.replay.play import render_trace


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bigfatfish.replay")
    parser.add_argument("fixture")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    fixture = Path(str(args.fixture))
    out = Path(str(args.out))
    text = "".join(f"{line}\n" for line in render_trace(load_jsonl(fixture)))
    out.write_text(text, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
