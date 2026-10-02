"""Layer 3 Groq LLM JSON extraction with deterministic mock fallback. TRD Sec 7.3."""
import re
from app.core.groq_client import groq_client
from app.prompts.templates import EXTRACTION_SYSTEM
from app.schemas.api import LLMExtraction

def mock_extract(clean_text: str, source_url: str):
    # Deterministic fallback: split sentences into candidate claims, extract hashtags/urls
    sents = [s.strip() for s in re.split(r"[.\n!?]+", clean_text or "") if len(s.strip()) > 20][:5]
    claims = [{"text": s[:500], "type": "factual", "evidence_spans": [s[:120]]} for s in sents]
    topics = list({w.lower() for w in re.findall(r"#(\w+)", clean_text or "")})[:10]
    urls = re.findall(r"https?://\S+", clean_text or "")[:10]
    if source_url and source_url not in urls:
        urls = [source_url] + urls
    return {"claims": claims, "topics": topics,
            "entities": [], "source_type": "news" if "rss" in (source_url or "") else "social/web",
            "stance_or_context": {}, "urls": urls, "temporal_expressions": [],
            "evidence_spans": [s[:200] for s in sents[:3]],
            "uncertainty": {"needs_review": True, "reasons": ["mock-extraction-no-groq-key"]},
            "_meta": {"model": "mock", "mock": True}}

def llm_extract(clean_text: str, source_meta: dict):
    from app.services.osint.relevance import strip_boilerplate_lines
    stripped, dropped = strip_boilerplate_lines(clean_text or "")
    use_text = stripped if stripped.strip() else (clean_text or "")
    user = f"SOURCE_URL: {source_meta.get('source_url')}\nPLATFORM: {source_meta.get('platform')}\nTEXT:\n{(use_text or '')[:8000]}"
    if not groq_client.available:
        d = mock_extract(use_text, source_meta.get("source_url", ""))
        d["_meta"]["boilerplate_lines_dropped"] = dropped
        return d
    try:
        data = groq_client.structured_extract(EXTRACTION_SYSTEM, user)
        # validate (non-strict: allow extra _meta)
        LLMExtraction.model_validate({k: v for k, v in data.items() if not k.startswith("_") or k == "_meta" if k != "_meta" or True})
        data["_meta"]["boilerplate_lines_dropped"] = dropped
        return data
    except Exception as e:
        d = mock_extract(use_text, source_meta.get("source_url", ""))
        d["uncertainty"] = {"needs_review": True, "reasons": [f"groq-fallback: {e}"]}
        d["_meta"] = {"model": groq_client.model, "mock": True, "fallback_error": str(e),
                      "boilerplate_lines_dropped": dropped}
        return d
