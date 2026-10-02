"""Tests for the local OCR service.

The critical behaviour is not "does OCR work" (that needs a real image and the
tesseract binary) but the guard rails: never promote a low-confidence or empty
reading into a post's text, and never claim a measurement that was not taken.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.ocr import service as S  # noqa: E402


def test_empty_image_is_reported_not_guessed():
    r = S.ocr_image(b"")
    assert r["available"] is False
    assert r["text"] == ""
    assert r["confidence"] is None
    assert r["error"] == "empty_image"


def test_garbage_bytes_do_not_raise():
    r = S.ocr_image(b"this is definitely not an image")
    assert r["available"] is False
    assert r["text"] == ""
    assert r["error"] and "image_decode_failed" in r["error"]


def test_low_confidence_is_never_promoted():
    # A confident-looking reading of a thin DOM text, but the engine was unsure.
    assert S.should_promote_ocr("", "some text", 0.30) is False
    assert S.should_promote_ocr("", "some text", 0.0) is False


def test_high_confidence_thin_dom_text_is_promoted():
    assert S.should_promote_ocr("", "भाजपा का मंत्री", 0.85) is True
    assert S.should_promote_ocr("short", "read text", 0.9) is True


def test_rich_dom_text_keeps_the_authors_words():
    long_dom = "Arrest Parvesh Verma. " * 4
    assert S.should_promote_ocr(long_dom, "image says something else", 0.95) is False


def test_empty_ocr_output_is_never_promoted():
    assert S.should_promote_ocr("", "", 0.99) is False
    assert S.should_promote_ocr("", None, 0.99) is False


def test_missing_confidence_blocks_promotion():
    # No measurement means no trust: the service must not assume it was high.
    assert S.should_promote_ocr("", "text without a score", None) is False


def test_engines_reports_what_is_actually_installed():
    avail = S.engines()
    assert isinstance(avail, list)
    for name in avail:
        assert name in ("tesseract", "macos-vision")


def test_result_shape_is_always_storable():
    r = S.ocr_image(b"\x00\x01\x02")
    for key in ("available", "engine", "text", "confidence", "lines", "line_count", "error"):
        assert key in r
    assert isinstance(r["lines"], list)
