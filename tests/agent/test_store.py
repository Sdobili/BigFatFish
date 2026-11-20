"""Undo restores the database and stops after ten minutes."""

import sqlite3
from pathlib import Path

from bigfatfish.agent.loop import Deliver, LoopEvent, initial, step
from bigfatfish.agent.store import CardDraft, CardStore
from bigfatfish.core.clock import FakeClock
from bigfatfish.core.events import GestureEvent, Observation, ProposalReady

_Snapshot = tuple[tuple[str, tuple[str, ...], tuple[tuple[object, ...], ...]], ...]


def test_undo_restores_snapshot(tmp_path: Path) -> None:
    clock = FakeClock(start_wall=1_700_000_000.0)
    db = tmp_path / "cards.sqlite"
    store = CardStore(db, clock)
    before = _snapshot(db)
    assert _cache_names(store) == ()
    effect = _deliver(0.0)
    store.add(_draft(effect, b"frame-a"), effect.token)
    assert _cache_names(store) == (effect.capture_id,)
    assert _snapshot(db) != before
    store.undo_last(clock.wall())
    assert _snapshot(db) == before, "snapshot after undo differs"
    assert _cache_names(store) == (), "screenshot cache file must be deleted"


def test_undo_after_10_minutes_refused(tmp_path: Path) -> None:
    clock = FakeClock(start_wall=1_700_000_000.0)
    db = tmp_path / "cards.sqlite"
    store = CardStore(db, clock)
    empty = _snapshot(db)
    first = _deliver(0.0)
    store.add(_draft(first, b"frame-a"), first.token)
    clock.advance(600)
    store.undo_last(clock.wall())
    assert _snapshot(db) == empty, "undo at 600s must remove the card"

    second = _deliver(10.0)
    store.add(_draft(second, b"frame-b"), second.token)
    clock.advance(600.001)
    kept = _snapshot(db)
    kept_files = _cache_names(store)
    store.undo_last(clock.wall())
    assert _snapshot(db) == kept, "undo after 10 minutes must be refused"
    assert _cache_names(store) == kept_files, "undo after 10 minutes must be refused"


def _deliver(t0: float) -> Deliver:
    state = initial()
    found: Deliver | None = None
    for event in _delivery_events(t0):
        state, effects = step(state, event)
        for effect in effects:
            if isinstance(effect, Deliver):
                found = effect
    assert found is not None
    return found


def _delivery_events(t0: float) -> list[LoopEvent]:
    first = (0.2, 0.2)
    second = (0.8, 0.6)
    return [
        GestureEvent(t=t0, kind="Wave", hand="right"),
        GestureEvent(t=t0 + 1.0, kind="Pointing_Up", hand="right", landmarks=(first,)),
        GestureEvent(t=t0 + 2.0, kind="Pointing_Up", hand="right", landmarks=(first,)),
        GestureEvent(t=t0 + 3.0, kind="Pointing_Up", hand="right", landmarks=(second,)),
        GestureEvent(t=t0 + 4.0, kind="Pointing_Up", hand="right", landmarks=(second,)),
        Observation(t=t0 + 4.5, window_title="Notes", text="buy milk"),
        GestureEvent(t=t0 + 5.0, kind="Thumb_Up", hand="right"),
        GestureEvent(t=t0 + 6.0, kind="Thumb_Up", hand="right"),
        ProposalReady(t=t0 + 6.5, text="todo: buy milk"),
        GestureEvent(t=t0 + 7.0, kind="Thumb_Up", hand="right"),
        GestureEvent(t=t0 + 8.0, kind="Thumb_Up", hand="right"),
    ]


def _draft(effect: Deliver, screenshot: bytes) -> CardDraft:
    return CardDraft(
        capture_id=effect.capture_id,
        window_title=effect.window_title,
        text=effect.text,
        proposal=effect.proposal,
        revisions=effect.revisions,
        screenshot=screenshot,
    )


def _snapshot(path: Path) -> _Snapshot:
    connection = sqlite3.connect(path)
    try:
        master = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()
        tables: list[tuple[str, tuple[str, ...], tuple[tuple[object, ...], ...]]] = []
        for item in master:
            name = item[0]
            if not isinstance(name, str):
                continue
            info = connection.execute(f"PRAGMA table_info({_quote(name)})").fetchall()
            columns = tuple(str(column[1]) for column in info)
            rows = connection.execute(
                f"SELECT * FROM {_quote(name)} ORDER BY rowid"
            ).fetchall()
            tables.append((name, columns, tuple(tuple(row) for row in rows)))
        return tuple(tables)
    finally:
        connection.close()


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _cache_names(store: CardStore) -> tuple[str, ...]:
    if not store.cache_dir.is_dir():
        return ()
    return tuple(
        sorted(path.name for path in store.cache_dir.iterdir() if path.is_file())
    )
