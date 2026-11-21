"""Read text from one captured image. CI uses FakeOcr."""

from typing import Protocol


class OcrError(RuntimeError):
    """The image was not read."""


class Ocr(Protocol):
    def read(self, image: bytes) -> str:
        """Return the text in one image."""
        ...


class FakeOcr:
    """Returns a fixed string and counts reads."""

    def __init__(self, text: str) -> None:
        self.calls = 0
        self.text = text

    def read(self, image: bytes) -> str:
        del image
        self.calls += 1
        return self.text


class RapidOcr:
    """RapidOCR reader. The package is optional and is not installed in CI."""

    def read(self, image: bytes) -> str:
        if not image:
            raise OcrError("empty image is not text")
        try:
            from rapidocr import RapidOCR  # type: ignore[import-not-found]
        except ImportError as exc:
            raise OcrError("rapidocr is not installed") from exc
        result = RapidOCR()(image)
        texts = getattr(result, "txts", None)
        if not texts:
            return ""
        lines = [str(item) for item in texts if str(item).strip()]
        return "\n".join(lines)
