"""Claim classification: type + relevance (items 1, 5, 6, 12, 13).

Deterministic, evidence-first:
- claim_type: factual | numerical | attribution | opinion | rhetoric | headline | metadata | boilerplate
- relevance: relevant | partially_relevant | irrelevant (vs investigation objective/entities)
- Semantic proxy: normalized unigram + bigram overlap weighted toward rare terms.
  Embedding-based similarity is the documented upgrade path (TRD future work);
  thresholds below are conservative so borderline claims stay partially_relevant.
"""
import re
import unicodedata
from collections import Counter

# ---------- boilerplate (pre-LLM strip + post-extraction validation, item 12) ----------
BOILERPLATE_PATTERNS = [
    r"skip to content", r"^sign in", r"^log in$", r"^subscribe", r"newsletter",
    r"cookie", r"all rights reserved", r"download (the|our) app", r"follow us",
    r"share via", r"^home$", r"^menu$", r"add .*trusted source", r"read more$",
    r"enjoy unlimited access", r"minimal ad experience", r"expertly crafted",
    r"news brief in summary", r"from wikipedia,? the free encyclopedia",
    r"jump to content", r"search search", r"languages?$", r"edition(\s+[A-Z]{2})?$",
    r"e-?paper", r"subscribe now", r"advertisement", r"login$", r"logout$",
    r"^(sat|sun|mon|tue|wed|thu|fri),?\s+\w+\s+\d{1,2},?\s+\d{4}$",
]
_BOILER_RE = re.compile("|".join(BOILERPLATE_PATTERNS), re.IGNORECASE)

_RHETORIC_PATTERNS = [
    r"fight to the finish", r"\bshame on\b", r"\bdown with\b", r"murdabad",
    r"zindabad", r"\blong live\b", r"^no justice", r"hai hai", r"hatao$",
    r"^a fight\b", r"do or die",
]
_RHETORIC_RE = re.compile("|".join(_RHETORIC_PATTERNS), re.IGNORECASE)

_ATTRIBUTION_RE = re.compile(
    r"\b(said|stated|announced|reported|claimed|alleged|according to|told|warned|demanded|urged|confirmed|denied)\b",
    re.IGNORECASE)
_NUMERICAL_RE = re.compile(
    r"\b\d[\d,]*(?:\.\d+)?\s*(%|percent|lakh|crore|thousand|million|billion|protesters?|people|students|devices|laptops?|tablets?|hours|days|years?)\b",
    re.IGNORECASE)
_OPINION_RE = re.compile(
    r"\b(i think|in my opinion|seems?|appears?|probably|should\b.*\bbe\b|must be stopped)\b",
    re.IGNORECASE)

_STOP = frozenset("""
with from that this have has are was were will would there their about into over under
claim case check verify investigation against which while during between through
what when where your more most such than then them they them its his her our your
the and for are but not you all any can had her was one our out day has have
""".split())


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    return re.sub(r"\s+", " ", s).strip().lower()


def _toks(s: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]{3,}", _norm(s)) if w not in _STOP]


def _bigrams(toks: list[str]) -> set[str]:
    return {f"{a} {b}" for a, b in zip(toks, toks[1:])}


def is_boilerplate(text: str) -> bool:
    """Post-extraction validation (item 12)."""
    t = (text or "").strip()
    if len(t) < 30:
        return True
    if _BOILER_RE.search(t):
        return True
    words = t.split()
    if len(words) <= 6 and ("/" in t or "(" in t):
        return True
    if len(words) <= 4:
        return True
    return False


def strip_boilerplate_lines(text: str) -> tuple[str, int]:
    """Pre-LLM filter (item 12): drop nav-chrome lines before Groq sees them."""
    lines = (text or "").splitlines()
    kept, dropped = [], 0
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if len(s) < 25 or _BOILER_RE.search(s):
            dropped += 1
            continue
        kept.append(ln)
    return "\n".join(kept), dropped


def classify_claim_type(text: str, llm_hint: str = "") -> tuple[str, str]:
    """Returns (claim_type, reason). LLM hint respected only if valid + consistent."""
    t = (text or "").strip()
    if is_boilerplate(t):
        # distinguish page-metadata from pure chrome
        if _BOILER_RE.search(t) or len(t.split()) <= 4:
            return "boilerplate", "matches boilerplate/nav-chrome pattern or too short"
        return "metadata", "page metadata, not a proposition"
    if _RHETORIC_RE.search(t):
        return "rhetoric", "rally slogan / rhetorical cry without verifiable proposition"
    if _NUMERICAL_RE.search(t):
        return "numerical", "contains quantified factual assertion"
    if _ATTRIBUTION_RE.search(t):
        return "attribution", "attributes proposition to a source"
    if _OPINION_RE.search(t):
        return "opinion", "opinion markers present"
    if "|" in t and len(t) < 140:
        return "headline", "pipe-separated headline shape"
    hint = (llm_hint or "").strip().lower()
    if hint in ("factual", "numerical", "attribution", "opinion", "rhetoric",
                "headline", "metadata", "boilerplate"):
        if hint == "rhetoric" and not _RHETORIC_RE.search(t):
            pass  # do not trust unsupported rhetoric hint
        else:
            return hint, "llm-provided type accepted"
    return "factual", "default: verifiable proposition"


def classify_relevance(text: str, claim_type: str, case_text: str,
                       case_keywords: list[str]) -> tuple[str, str, float]:
    """Returns (relevance, reason, score). Score = rare-term unigram+bigram overlap."""
    if claim_type in ("boilerplate", "metadata"):
        return "irrelevant", f"claim_type={claim_type} can never answer the objective", 0.0
    ct, kt = _toks(text), _toks(" ".join(case_keywords or []) + " " + (case_text or ""))
    if not ct or not kt:
        return "irrelevant", "no comparable terms", 0.0
    kfreq = Counter(kt)
    rarity = {w: 1.0 / (1.0 + kfreq.get(w, 0)) for w in set(kt) | set(ct)}
    overlap = set(ct) & set(kt)
    uni = sum(rarity[w] for w in overlap)
    bi = len(_bigrams(ct) & _bigrams(kt)) * 1.5
    denom = sum(rarity[w] for w in set(ct)) or 1.0
    score = round((uni + bi) / denom, 3)
    shared = sorted(overlap, key=lambda w: -rarity[w])[:6]
    if claim_type == "rhetoric":
        if score >= 0.15:
            return "partially_relevant", f"rhetoric; topical overlap ({', '.join(shared) or 'weak'})", score
        return "irrelevant", "rhetoric without topical overlap", score
    if claim_type == "opinion":
        if score >= 0.3:
            return "partially_relevant", f"opinion with topical overlap ({', '.join(shared)})", score
        return "irrelevant", "opinion without topical overlap", score
    if score >= 0.3 or len(overlap) >= 3:
        return "relevant", f"topical/entity overlap ({', '.join(shared) or 'terms'})", score
    if score >= 0.12 or len(overlap) >= 1:
        return "partially_relevant", "weak but non-zero topical overlap", score
    return "irrelevant", "no meaningful relationship to objective/entities", score


def classify(text: str, case_text: str, case_keywords: list[str],
             llm_hint: str = "") -> dict:
    ctype, type_reason = classify_claim_type(text, llm_hint)
    rel, rel_reason, score = classify_relevance(text, ctype, case_text, case_keywords)
    return {"claim_type": ctype, "type_reason": type_reason, "relevance": rel,
            "relevance_reason": rel_reason, "relevance_score": score}
