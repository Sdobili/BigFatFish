"""Open-palm waves need two direction reversals inside 1.5s."""

from bigfatfish.core.events import GestureEvent
from bigfatfish.perception.wave import WaveDetector

_WRIST = 0


def _palm(
    t: float,
    x: float,
    *,
    kind: str = "Open_Palm",
    landmarks: tuple[tuple[float, float, float], ...] | None = None,
    with_landmarks: bool = True,
) -> GestureEvent:
    points = landmarks
    if with_landmarks and points is None:
        points = tuple(
            (x, 0.1, 0.0) if index == _WRIST else (0.4, 0.4, 0.0) for index in range(21)
        )
    return GestureEvent(t=t, kind=kind, hand="right", landmarks=points, score=0.9)


def _feed(
    samples: list[tuple[float, float]], **kwargs: object
) -> list[GestureEvent | None]:
    detector = WaveDetector()
    return [detector.feed(_palm(t, x, **kwargs)) for t, x in samples]


def test_two_reversals_within_window_is_wave() -> None:
    samples = [(0.0, 0.2), (0.25, 0.8), (0.5, 0.2), (1.0, 0.8)]
    results = _feed(samples)
    hit = results[-1]
    assert hit is not None
    assert hit.kind == "Wave"
    assert hit.t == 1.0
    assert hit.hand == "right"
    assert all(item is None for item in results[:-1])


def test_reversals_exactly_at_window_are_wave() -> None:
    # Reversals at t=0.5 and t=2.0 are exactly 1.5s apart, so the window is closed.
    samples = [(0.0, 0.2), (0.25, 0.8), (0.5, 0.2), (2.0, 0.8)]
    results = _feed(samples)
    hit = results[-1]
    assert hit is not None
    assert hit.kind == "Wave"
    assert hit.t == 2.0
    assert all(item is None for item in results[:-1])


def test_single_swipe_is_not_wave() -> None:
    # Right, then left: exactly one reversal. Zero reversals would not kill a
    # threshold lowered from 2 to 1.
    samples = [(0.0, 0.2), (0.3, 0.8), (0.6, 0.2)]
    results = _feed(samples)
    assert all(item is None for item in results), "single swipe is not a wave"


def test_static_open_palm_is_not_wave() -> None:
    samples = [(0.0, 0.4), (0.5, 0.4), (1.0, 0.4), (1.5, 0.4)]
    results = _feed(samples)
    assert all(item is None for item in results)


def test_slow_reversals_are_not_wave() -> None:
    # Two reversals, at t=0.5 and t=2.25, sit 1.75s apart.
    samples = [(0.0, 0.2), (0.25, 0.8), (0.5, 0.2), (2.25, 0.8)]
    results = _feed(samples)
    assert all(item is None for item in results), "slow reversals are not a wave"


def test_non_open_palm_is_not_wave() -> None:
    samples = [(0.0, 0.2), (0.25, 0.8), (0.5, 0.2), (1.0, 0.8)]
    for kind in ("Pointing_Up", "Thumb_Up", "Closed_Fist", "Victory"):
        results = _feed(samples, kind=kind)
        assert all(item is None for item in results)


def test_open_palm_without_landmarks_is_not_wave() -> None:
    samples = [(0.0, 0.2), (0.25, 0.8), (0.5, 0.2), (1.0, 0.8)]
    missing = _feed(samples, with_landmarks=False)
    empty = _feed(samples, landmarks=())
    assert all(item is None for item in missing)
    assert all(item is None for item in empty)


def test_zero_delta_is_not_a_reversal() -> None:
    # The repeated x is Δx == 0. Counting it would make a second reversal.
    samples = [(0.0, 0.2), (0.2, 0.8), (0.4, 0.8), (0.6, 0.3)]
    results = _feed(samples)
    assert all(item is None for item in results)


def test_detector_resets_after_a_wave() -> None:
    detector = WaveDetector()
    first = [(0.0, 0.2), (0.2, 0.8), (0.4, 0.2), (0.6, 0.8)]
    first_hits = [detector.feed(_palm(t, x)) for t, x in first]
    assert first_hits[-1] is not None and first_hits[-1].kind == "Wave"
    # Full reset: the next three samples are a seed, one direction, one reversal.
    quiet = [(0.8, 0.2), (1.0, 0.8), (1.2, 0.2)]
    assert all(detector.feed(_palm(t, x)) is None for t, x in quiet)
    again = [(1.4, 0.8), (1.6, 0.2), (1.8, 0.8)]
    again_hits = [detector.feed(_palm(t, x)) for t, x in again]
    assert again_hits[-1] is not None and again_hits[-1].kind == "Wave"
    assert all(item is None for item in again_hits[:-1])
