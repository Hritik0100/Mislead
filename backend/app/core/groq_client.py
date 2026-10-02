"""Groq LLM client wrapper. PRD Sec 9, TRD Sec 8.
Backend-only key, exponential backoff, structured JSON enforcement, metadata persistence.
Uses direct HTTPS REST (httpx) — no groq-SDK/httpx version coupling.
Falls back to deterministic mock extractor when no API key (for local dev/MVP).
"""
import json
import time
import uuid
from typing import Dict, Any
import httpx
from app.core.config import settings

API_URL = "https://api.groq.com/openai/v1/chat/completions"

class GroqClient:
    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.model = settings.GROQ_MODEL

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def structured_extract(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Call Groq with JSON-only enforcement + retries. Returns dict with _meta."""
        request_id = str(uuid.uuid4())
        started = time.time()
        if not self.available:
            raise RuntimeError("GROQ_API_KEY not configured")
        last_err = None
        for attempt in range(settings.GROQ_MAX_RETRIES):
            try:
                with httpx.Client(timeout=settings.GROQ_TIMEOUT) as client:
                    r = client.post(
                        API_URL,
                        headers={"Authorization": f"Bearer {self.api_key}",
                                 "Content-Type": "application/json"},
                        json={"model": self.model,
                              "messages": [{"role": "system", "content": system_prompt},
                                           {"role": "user", "content": user_prompt}],
                              "temperature": 0.0,
                              "response_format": {"type": "json_object"}},
                    )
                    r.raise_for_status()
                    body = r.json()
                raw = body["choices"][0]["message"]["content"]
                data = json.loads(raw)
                data["_meta"] = {
                    "model": self.model,
                    "request_id": request_id,
                    "latency_ms": int((time.time() - started) * 1000),
                    "attempt": attempt + 1,
                    "mock": False,
                    "usage": body.get("usage"),
                }
                return data
            except Exception as e:
                last_err = e
                time.sleep(2 ** attempt)
        raise RuntimeError(f"Groq call failed after retries: {last_err}")

groq_client = GroqClient()
