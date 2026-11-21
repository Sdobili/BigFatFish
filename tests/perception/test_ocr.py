"""RapidOCR must not look installed when the package is absent."""

import pytest

from bigfatfish.perception.ocr import OcrError, RapidOcr


def test_rapidocr_missing_is_not_empty_text() -> None:
    try:
        import rapidocr  # noqa: F401
    except ImportError:
        pass
    else:
        pytest.skip("rapidocr is installed")
    with pytest.raises(OcrError, match="rapidocr is not installed"):
        RapidOcr().read(b"not-an-image")
