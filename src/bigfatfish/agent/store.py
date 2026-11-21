"""SQLite cards, a screenshot cache, and an append-only command log."""

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from bigfatfish.agent.loop import ConfirmationToken
from bigfatfish.core.clock import Clock

_UNDO_WINDOW_S = 600.0


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
        self._spent = set[int]()
        self.cache_dir = path.parent / "cache"
        self._log_path = path.with_name(path.name + ".log")
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
        if not isinstance(token, ConfirmationToken):
            raise TypeError("confirmation required")
        self._consume_token(draft, token)
        _AddCard(draft, self._clock.wall()).do(self)

    def _consume_token(self, draft: CardDraft, token: object) -> None:
        if token is not None and getattr(token, "_minted", None) is not True:
            raise TypeError("forged confirmation token")
        if getattr(token, "_capture_id", draft.capture_id) != draft.capture_id:
            raise TypeError("confirmation token capture mismatch")
        if id(token) in self._spent:
            raise TypeError("confirmation token already used")
        self._spent.add(id(token))

    def undo_last(self, now_wall: float) -> None:
        card = self._latest()
        if card is None:
            return
        if now_wall - card.created_at > _UNDO_WINDOW_S:
            return
        draft = CardDraft(
            capture_id=card.capture_id,
            window_title=card.window_title,
            text=card.text,
            proposal=card.proposal,
            revisions=card.revisions,
            screenshot=b"",
        )
        _AddCard(draft, card.created_at).undo(self)

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

    def _latest(self) -> Card | None:
        connection = self._connect()
        try:
            row = connection.execute(
                """
                SELECT
                    id, created_at, capture_id, window_title, text, proposal, revisions
                FROM cards
                ORDER BY rowid DESC
                LIMIT 1
                """
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            return None
        return _card_from_row(row)

    def _insert(self, draft: CardDraft, created_at: float) -> None:
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

    def _delete_card(self, card_id: str) -> None:
        connection = self._connect()
        try:
            connection.execute("DELETE FROM cards WHERE id = ?", (card_id,))
            connection.commit()
        finally:
            connection.close()

    def _write_cache(self, draft: CardDraft) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        (self.cache_dir / draft.capture_id).write_bytes(draft.screenshot)

    def _remove_cache(self, capture_id: str) -> None:
        (self.cache_dir / capture_id).unlink(missing_ok=True)

    def _append_log(self, op: str, card_id: str) -> None:
        line = json.dumps({"op": op, "id": card_id}, ensure_ascii=True)
        with self._log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)


class _AddCard:
    def __init__(self, draft: CardDraft, created_at: float) -> None:
        self._draft = draft
        self._created_at = created_at

    def do(self, store: CardStore) -> None:
        store._insert(self._draft, self._created_at)
        store._write_cache(self._draft)
        store._append_log("add", self._draft.capture_id)

    def undo(self, store: CardStore) -> None:
        store._append_log("undo", self._draft.capture_id)
        store._delete_card(self._draft.capture_id)
        store._remove_cache(self._draft.capture_id)


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
