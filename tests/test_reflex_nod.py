"""A closed fist cancels. Only a thumb-up nods."""

from bigfatfish.core.events import GestureEvent
from bigfatfish.reflex.state import initial, step


def test_closed_fist_does_not_nod_and_thumb_up_does() -> None:
    after_thumb = step(
        initial(),
        GestureEvent(t=0.5, kind="Thumb_Up", hand="right"),
    )
    assert after_thumb.nodding is True
    assert after_thumb.nods == 1

    after_fist = step(
        after_thumb,
        GestureEvent(t=2.0, kind="Closed_Fist", hand="left"),
    )
    assert after_fist.nodding is False
    assert after_fist.nods == 1
