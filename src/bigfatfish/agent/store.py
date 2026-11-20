"""SQLite cards and a screenshot cache. Undo does nothing in this stub."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from bigfatfish.core.clock import Clock


@dataclass(frozen=True, slots=True)
class CardDraft:
    capture_id: str
    window_title: str
    text: str
    proposal: str
    revisions: int
    screenshot: bytes


@dataclass(frozen=True, slots=True)
class Card:
    id: str
    created_at: float
    capture_id: str
    window_title: str
    text: str
    proposal: str
    revisions: int


class CardStore:
    def __init__(self, path: Path, clock: Clock) -> None:
        self._path = path
        self._clock = clock
        self.cache_dir = path.parent / "cache"
        connection = self._connect()
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cards (
                    id TEXT PRIMARY KEY,
                    created_at REAL NOT NULL,
                    capture_id TEXT NOT NULL,
                    window_title TEXT NOT NULL,
                    text TEXT NOT NULL,
                    proposal TEXT NOT NULL,
                    revisions INTEGER NOT NULL
                )
                """
            )
            connection.commit()
        finally:
            connection.close()

    def add(self, draft: CardDraft, token: object) -> None:
        del token
        created_at = self._clock.wall()
        connection = self._connect()
        try:
            connection.execute(
                """
                INSERT INTO cards (
                    id, created_at, capture_id, window_title, text, proposal, revisions
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft.capture_id,
                    created_at,
                    draft.capture_id,
                    draft.window_title,
                    draft.text,
                    draft.proposal,
                    draft.revisions,
                ),
            )
            connection.commit()
        finally:
            connection.close()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        (self.cache_dir / draft.capture_id).write_bytes(draft.screenshot)

    def undo_last(self, now_wall: float) -> None:
        return

    def recent(self, n: int) -> list[Card]:
        if n < 1:
            return []
        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT
                    id, created_at, capture_id, window_title, text, proposal, revisions
                FROM cards
                ORDER BY created_at DESC, rowid DESC
                LIMIT ?
                """,
                (n,),
            ).fetchall()
        finally:
            connection.close()
        return [_card_from_row(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)


def _card_from_row(row: object) -> Card:
    if not isinstance(row, tuple) or len(row) != 7:
        raise TypeError("cards row has an unexpected shape")
    card_id, created_at, capture_id, window_title, text, proposal, revisions = row
    if (
        not isinstance(card_id, str)
        or not isinstance(created_at, float)
        or not isinstance(capture_id, str)
        or not isinstance(window_title, str)
        or not isinstance(text, str)
        or not isinstance(proposal, str)
        or not isinstance(revisions, int)
    ):
        raise TypeError("cards row has an unexpected type")
    return Card(
        id=card_id,
        created_at=created_at,
        capture_id=capture_id,
        window_title=window_title,
        text=text,
        proposal=proposal,
        revisions=revisions,
    )
