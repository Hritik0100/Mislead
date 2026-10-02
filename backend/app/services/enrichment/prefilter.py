"""Layer 1 pre-filter: normalize, keyword match, exact-dedup. TRD Sec 7.1."""
import hashlib, re, unicodedata

def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s

def content_hash(s: str) -> str:
    return hashlib.sha256(normalize(s).encode()).hexdigest()

def prefilter(text: str, keywords: list) -> tuple[bool, str]:
    n = normalize(text)
    if not n:
        return False, "empty"
    if not keywords:
        return True, "no-keywords-allow-all"
    for kw in keywords:
        if normalize(kw) and normalize(kw) in n:
            return True, f"match:{kw}"
    return False, "no-keyword-match"
