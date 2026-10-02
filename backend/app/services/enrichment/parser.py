"""Layer 2 clean text: HTML/XML parse, preserve provenance. TRD Sec 7.2."""
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def clean_html(raw_html: str, base_url: str = ""):
    if not raw_html:
        return {"clean_text": "", "title": "", "links": [], "author": ""}
    soup = BeautifulSoup(raw_html, "lxml")
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    links = []
    for a in soup.find_all("a", href=True):
        try:
            links.append(urljoin(base_url, a["href"]))
        except Exception:
            pass
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return {"clean_text": "\n".join(lines)[:20000], "title": title, "links": links[:100], "author": ""}
