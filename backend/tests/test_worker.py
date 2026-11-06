import cv2
import pytest

from backend.worker import inspect_video


@pytest.mark.parametrize("change,first_frame,expected", [
    ({cv2.CAP_PROP_FPS: 0}, True, "no readable"),
    ({cv2.CAP_PROP_FRAME_COUNT: 1801}, True, "60 seconds"),
    ({cv2.CAP_PROP_FPS: 120}, True, "60 frames"),
    ({cv2.CAP_PROP_FRAME_WIDTH: 7680}, True, "4K"),
    ({}, False, "first video frame"),
])
def test_decoded_video_checks_reject_excessive_or_unreadable_inputs(monkeypatch, change, first_frame, expected):
    props = {cv2.CAP_PROP_FRAME_COUNT: 300, cv2.CAP_PROP_FPS: 30,
             cv2.CAP_PROP_FRAME_WIDTH: 1920, cv2.CAP_PROP_FRAME_HEIGHT: 1080, **change}
    class Capture:
        released = False
        def isOpened(self): return True
        def get(self, key): return props[key]
        def read(self): return first_frame, object() if first_frame else None
        def release(self): self.released = True
    capture = Capture()
    monkeypatch.setattr(cv2, "VideoCapture", lambda _: capture)
    with pytest.raises(ValueError, match=expected):
        inspect_video("fixture.mp4")
    assert capture.released
