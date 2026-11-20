"""Recognizer results become GestureEvents without importing mediapipe."""


class _Category:
    def __init__(self, category_name: str, score: float) -> None:
        self.index = 0
        self.score = score
        self.display_name = category_name
        self.category_name = category_name


class _Point:
    def __init__(self, x: float, y: float, z: float) -> None:
        self.x = x
        self.y = y
        self.z = z


class _Result:
    def __init__(
        self,
        gestures: list[list[_Category]],
        handedness: list[list[_Category]],
        hand_landmarks: list[list[_Point]],
    ) -> None:
        self.gestures = gestures
        self.handedness = handedness
        self.hand_landmarks = hand_landmarks
        self.hand_world_landmarks: list[list[_Point]] = []


def _points(count: int) -> list[_Point]:
    return [
        _Point(x=index / 100, y=(index + 1) / 100, z=(index + 2) / 100)
        for index in range(count)
    ]


def _hand(
    *,
    gesture: str,
    gesture_score: float,
    hand: str,
    hand_score: float = 0.99,
    point_count: int = 21,
) -> _Result:
    return _Result(
        gestures=[[_Category(gesture, gesture_score)]],
        handedness=[[_Category(hand, hand_score)]],
        hand_landmarks=[_points(point_count)],
    )


def test_high_score_hand_emits_event() -> None:
    from bigfatfish.perception.gestures import to_events

    events = to_events(
        _hand(gesture="Pointing_Up", gesture_score=0.8, hand="Right"),
        t=1.25,
        min_hand_score=0.5,
    )
    assert len(events) == 1
    event = events[0]
    assert event.t == 1.25
    assert event.kind == "Pointing_Up"
    assert event.hand == "right"
    assert event.score == 0.8
    assert event.landmarks is not None
    assert len(event.landmarks) == 21
    assert event.landmarks[0] == (0.0, 0.01, 0.02)
    assert event.landmarks[20] == (0.2, 0.21, 0.22)


def test_score_equal_to_threshold_is_kept() -> None:
    from bigfatfish.perception.gestures import to_events

    events = to_events(
        _hand(gesture="Victory", gesture_score=0.5, hand="Right"),
        t=0.0,
        min_hand_score=0.5,
    )
    assert len(events) == 1
    assert events[0].kind == "Victory"


def test_low_score_hand_dropped() -> None:
    from bigfatfish.perception.gestures import to_events

    events = to_events(
        _hand(gesture="Open_Palm", gesture_score=0.49, hand="Left"),
        t=0.0,
        min_hand_score=0.5,
    )
    assert events == [], "low score hand must be dropped"


def test_hand_is_lowercase() -> None:
    from bigfatfish.perception.gestures import to_events

    events = to_events(
        _hand(gesture="Thumb_Up", gesture_score=0.95, hand="Left"),
        t=0.0,
        min_hand_score=0.5,
    )
    assert len(events) == 1
    assert events[0].hand == "left", "hand must be lowercase"


def test_no_hand_emits_nothing() -> None:
    from bigfatfish.perception.gestures import to_events

    result = _Result(gestures=[], handedness=[], hand_landmarks=[])
    assert to_events(result, t=0.0, min_hand_score=0.5) == []
