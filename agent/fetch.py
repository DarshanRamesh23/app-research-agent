import hashlib, json, os
import httpx
from bs4 import BeautifulSoup

CACHE = "data/cache"
os.makedirs(CACHE, exist_ok=True)
HEADERS = {"User-Agent": "Mozilla/5.0 (research-agent; take-home)"}

def _path(url):
    return os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest() + ".json")

def fetch(url, max_chars=40000):
    """Return {url, status, text}. Cached, so reruns are free and reproducible."""
    p = _path(url)
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    try:
        r = httpx.get(url, headers=HEADERS, timeout=20, follow_redirects=True)
        text = ""
        if r.status_code == 200 and "html" in r.headers.get("content-type", ""):
            soup = BeautifulSoup(r.text, "lxml")
            for t in soup(["script", "style", "nav", "footer"]):
                t.decompose()
            text = " ".join(soup.get_text(" ").split())[:max_chars]
        elif r.status_code == 200:
            text = r.text[:max_chars]
        out = {"url": str(r.url), "status": r.status_code, "text": text}
    except Exception as e:
        out = {"url": url, "status": 0, "text": "", "error": str(e)[:100]}
    json.dump(out, open(p, "w", encoding="utf-8"))
    return out