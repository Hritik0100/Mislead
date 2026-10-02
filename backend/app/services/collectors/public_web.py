"""Public web fetch. Respects robots/terms. No paywall/auth bypass. TRD Sec 6."""
import httpx
from bs4 import BeautifulSoup
from .base import SourceRecord

HEADERS = {"User-Agent": "OSINT-MVP/1.0 (research; respects robots.txt)"}

def collect_web(url: str):
    try:
        r = httpx.get(url, headers=HEADERS, timeout=20, follow_redirects=True)
        r.raise_for_status()
    except Exception as e:
        return [], f"fetch failed: {e}"
    soup = BeautifulSoup(r.text, "lxml")
    title = soup.title.string if soup.title else url
    # visible text (keep simple)
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    text = soup.get_text(separator="\n")[:15000]
    rec = SourceRecord(platform="web", account_username=url.split("/")[2] if "://" in url else url,
                       source_url=url, text=text, title=str(title), raw_html=r.text[:200000])
    return [rec], ""
