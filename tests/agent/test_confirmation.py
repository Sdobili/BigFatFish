"""A card is written only after the loop issues a confirmation token."""

import sqlite3
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from bigfatfish.agent.loop import (
    ConfirmationToken,
    Deliver,
    LoopEvent,
    initial,
    step,
)
from bigfatfish.agent.store import CardDraft, CardStore
from bigfatfish.core.clock import FakeClock
from bigfatfish.core.events import GestureEvent, Observation, ProposalReady, Tick

_KINDS = (
    "Open_Palm",
    "Closed_Fist",
    "Pointing_Up",
    "Thumb_Up",
    "Thumb_Down",
    "Victory",
    "ILoveYou",
    "Wave",
    "None",
)
_Snapshot = tuple[tuple[str, tuple[str, ...], tuple[tuple[object, ...], ...]], ...]
_View = tuple[_Snapshot, tuple[str, ...]]


def test_token_cannot_be_constructed() -> None:
    with pytest.raises(TypeError):
        ConfirmationToken()


def _sequences() -> st.SearchStrategy[list[LoopEvent]]:
    gesture = st.builds(
        GestureEvent,
        t=st.integers(min_value=0, max_value=40).map(float),
        kind=st.sampled_from(_KINDS),
        hand=st.sampled_from(("left", "right")),
        landmarks=st.one_of(st.none(), st.just(((0.2, 0.2),)), st.just(((0.8, 0.6),))),
        score=st.one_of(st.none(), st.just(0.0), st.just(0.9)),
    )
    tick = st.builds(Tick, t=st.integers(min_value=0, max_value=40).map(float))
    observation = st.builds(
        Observation,
        t=st.integers(min_value=0, max_value=40).map(float),
        window_title=st.just("Notes"),
        text=st.just("buy milk"),
    )
    proposal = st.builds(
        ProposalReady,
        t=st.integers(min_value=0, max_value=40).map(float),
        text=st.just("todo: buy milk"),
    )
    event = st.one_of(gesture, tick, observation, proposal)
    random_events = st.lists(event, max_size=8)
    confirmed = st.just(_delivery_events(0.0))
    return st.one_of(
        random_events,
        st.tuples(confirmed, random_events).map(
            lambda parts: list(parts[0]) + list(parts[1])
        ),
    )


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


@given(events=_sequences())
@settings(max_examples=1000, derandomize=True, deadline=None, database=None)
def test_no_write_without_confirmation(events: list[LoopEvent]) -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        db = root / "cards.sqlite"
        store = CardStore(db, FakeClock(start_wall=1_700_000_000.0))
        before = _view(store, db)
        state = initial()
        writes = 0
        for event in events:
            state, effects = step(state, event)
            delivers = [effect for effect in effects if isinstance(effect, Deliver)]
            if not delivers:
                continue
            if not isinstance(event, GestureEvent) or event.kind != "Thumb_Up":
                raise AssertionError("write without confirmation")
            for effect in delivers:
                store.add(_draft(effect, writes), effect.token)
                writes += 1
        if writes == 0:
            assert _view(store, db) == before, "write without confirmation"
        assert _card_count(_snapshot(db)) == writes, "write without confirmation"
        mid = _view(store, db)
        try:
            store.add(_unconfirmed(), None)
        except TypeError:
            pass
        assert _view(store, db) == mid, "write without confirmation"


def _draft(effect: Deliver, index: int) -> CardDraft:
    return CardDraft(
        capture_id=f"cap-{index}",
        window_title=effect.window_title,
        text=effect.text,
        proposal=effect.proposal,
        revisions=effect.revisions,
        screenshot=b"frame",
    )


def _unconfirmed() -> CardDraft:
    return CardDraft(
        capture_id="unconfirmed",
        window_title="Notes",
        text="buy milk",
        proposal="todo: buy milk",
        revisions=0,
        screenshot=b"nope",
    )


def _view(store: CardStore, db: Path) -> _View:
    return (_snapshot(db), _cache_names(store))


def _card_count(snapshot: _Snapshot) -> int:
    return sum(len(rows) for name, _columns, rows in snapshot if name == "cards")


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
            quoted = '"' + name.replace('"', '""') + '"'
            info = connection.execute(f"PRAGMA table_info({quoted})").fetchall()
            columns = tuple(str(column[1]) for column in info)
            rows = connection.execute(
                f"SELECT * FROM {quoted} ORDER BY rowid"
            ).fetchall()
            tables.append((name, columns, tuple(tuple(row) for row in rows)))
        return tuple(tables)
    finally:
        connection.close()


def _cache_names(store: CardStore) -> tuple[str, ...]:
    if not store.cache_dir.is_dir():
        return ()
    return tuple(
        sorted(path.name for path in store.cache_dir.iterdir() if path.is_file())
    )
