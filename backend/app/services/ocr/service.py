"""Local OCR for image-borne text.

Why: a large share of social misinformation is an image - a poster, meme or
screenshot. The DOM text for such a post is empty or a fragment, so the claim
itself only exists as pixels. Reading it makes the post searchable and quotable.

Engines, in order of preference:

1. Tesseract (`-l hin+eng`). Primary. Handles Devanagari *and* Latin, which
   matters because Indian misinformation posters mix Hindi headlines with
   English terms ("Gen Z", "directed-energy weapons"). Installed via
   `brew install tesseract tesseract-lang`.
2. macOS Vision via `ocrmac`. Fallback with no external binary, but this build's
   recognition languages do NOT include Hindi - measured on a Hindi poster it
   returned a single 0.30-confidence garbage line. It is therefore only trusted
   for Latin text, and the result records which engine produced it.

Both run on-device. No image is sent to a third-party OCR API.

`confidence` is a real measurement from the engine (Tesseract per-word mean,
Vision per-observation mean), never invented, so a caller can refuse to promote
low-confidence output into a post's text.
"""
import io
import os
import shutil
import subprocess
import tempfile
from typing import Any, Optional

# Below this many characters of DOM text a post counts as "no real caption", so
# OCR output may be promoted to be the post's text.
MIN_DOM_TEXT_FOR_CAPTION = 25
# OCR output below this mean confidence is treated as unreliable and is recorded
# but not promoted into the post text.
MIN_PROMOTABLE_CONFIDENCE = 0.55
# Per-word floor: tokens below this are treated as misreads and discarded.
MIN_WORD_CONFIDENCE = 0.55
TESSERACT_BIN = os.environ.get("TESSERACT_BIN") or shutil.which("tesseract") or ""
TESS_LANGS = os.environ.get("TESSERACT_LANGS", "hin+eng")


def _fail(err: str, engine: Optional[str] = None) -> dict:
    return {"available": False, "engine": engine, "text": "", "confidence": None,
            "lines": [], "line_count": 0, "error": err}


def engines() -> list:
    out = []
    if TESSERACT_BIN and os.path.exists(TESSERACT_BIN):
        out.append("tesseract")
    try:
        from ocrmac.ocrmac import text_from_image  # noqa: F401
        out.append("macos-vision")
    except Exception:
        pass
    return out


def _ocr_tesseract(data: bytes) -> dict:
    """Grayscale + two page-segmentation modes; keep the better reading.

    Measured on a Hindi/English poster: plain grayscale with psm 6/11 recovered
    the headline, while thresholding and 2x upscaling degraded it.
    """
    try:
        from PIL import Image, ImageOps
    except Exception as e:
        return _fail(f"pillow_unavailable: {type(e).__name__}")
    try:
        img = ImageOps.autocontrast(Image.open(io.BytesIO(data)).convert("L"))
        img.load()
    except Exception as e:
        return _fail(f"image_decode_failed: {type(e).__name__}")

    best: Optional[dict] = None
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "in.png")
        img.save(path)
        for psm in ("6", "11"):
            try:
                r = subprocess.run(
                    [TESSERACT_BIN, path, "stdout", "-l", TESS_LANGS, "--psm", psm, "tsv"],
                    capture_output=True, text=True, timeout=120,
                )
            except Exception as e:
                return _fail(f"tesseract_failed: {type(e).__name__}")
            if r.returncode != 0 and not r.stdout:
                continue
            lines, confs = [], []
            for row in r.stdout.splitlines()[1:]:
                parts = row.split("\t")
                if len(parts) < 12:
                    continue
                word = parts[11].strip()
                try:
                    conf = float(parts[10])
                except ValueError:
                    continue
                if not word or conf < 0:
                    continue
                lines.append({"text": word, "confidence": round(conf / 100.0, 4)})
                confs.append(conf / 100.0)
            if not lines:
                continue
            # Drop low-confidence tokens. On a photo post the background
            # contributes junk ("= do Hy)") that otherwise drags the mean down
            # and buries the headline that was actually read correctly.
            kept = [l for l in lines if l["confidence"] >= MIN_WORD_CONFIDENCE]
            if len(kept) < 3:
                kept = lines
            confs = [l["confidence"] for l in kept]
            cand = {
                "available": True, "engine": "tesseract", "psm": psm,
                "text": " ".join(l["text"] for l in kept),
                "confidence": round(sum(confs) / len(confs), 4),
                "lines": kept, "line_count": len(kept), "error": None,
            }
            # Prefer the reading that recognised the most solid words, then the
            # more confident one. Word count alone picked a noisy sparse mode.
            if best is None or (cand["line_count"], cand["confidence"]) > \
                               (best["line_count"], best["confidence"]):
                best = cand
    if best is None:
        return _fail("tesseract_no_text", "tesseract")
    return best


def _ocr_vision(data: bytes) -> dict:
    try:
        from PIL import Image
        from ocrmac.ocrmac import text_from_image
    except Exception as e:
        return _fail(f"engine_unavailable: {type(e).__name__}")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
        res = text_from_image(img, recognition_level="accurate",
                              language_preference=None, detail=True)
    except Exception as e:
        return _fail(f"ocr_failed: {type(e).__name__}: {str(e)[:100]}", "macos-vision")
    lines, confs = [], []
    for row in res or []:
        try:
            t, c = (row[0] or "").strip(), float(row[1])
        except Exception:
            continue
        if not t:
            continue
        lines.append({"text": t, "confidence": round(c, 4),
                      "box": [round(float(v), 1) for v in row[3]] if len(row) > 3 and row[3] else None})
        confs.append(c)
    if not lines:
        return {"available": True, "engine": "macos-vision", "text": "", "confidence": None,
                "lines": [], "line_count": 0, "error": None}
    return {"available": True, "engine": "macos-vision",
            "text": "\n".join(l["text"] for l in lines),
            "confidence": round(sum(confs) / len(confs), 4),
            "lines": lines, "line_count": len(lines), "error": None}


def ocr_image(data: bytes, languages: Optional[list] = None) -> dict:
    """Run OCR on image bytes. Always returns a storable dict."""
    if not data:
        return _fail("empty_image")
    if TESSERACT_BIN and os.path.exists(TESSERACT_BIN):
        res = _ocr_tesseract(data)
        if res.get("text"):
            return res
        # Fall through to Vision if Tesseract found nothing at all.
        v = _ocr_vision(data)
        if v.get("text"):
            v["note"] = "tesseract returned no text; used macos-vision (no Hindi support)"
            return v
        return res
    return _ocr_vision(data)


def should_promote_ocr(dom_text: str, ocr_text: str, confidence: Optional[float] = None) -> bool:
    """True when OCR output is trustworthy enough to stand in for a caption.

    A missing score is treated as untrustworthy rather than as "probably fine":
    both engines always report a confidence when they return text, so `None`
    means something went wrong and the reading should not be promoted.
    """
    if not ocr_text:
        return False
    if confidence is None or confidence < MIN_PROMOTABLE_CONFIDENCE:
        return False
    return len((dom_text or "").strip()) < MIN_DOM_TEXT_FOR_CAPTION
