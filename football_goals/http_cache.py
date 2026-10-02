"""HTTP GET with retries/backoff and a timestamped on-disk cache of every raw
download, so any run can be audited later ("what exactly did we see?")."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

log = logging.getLogger(__name__)
CACHE_DIR = Path(__file__).parent / "cache"
UA = {"User-Agent": "Mozilla/5.0 (pitchside football_goals; weekly analysis)"}


class FetchError(RuntimeError):
    pass


def _cache_name(url: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", url.split("://", 1)[-1])[:80]
    return f"{slug}_{hashlib.sha1(url.encode()).hexdigest()[:8]}"


def fetch(url: str, *, params=None, headers=None, retries: int = 4, backoff: float = 2.0,
          timeout: int = 30, session=None) -> requests.Response:
    """GET with exponential backoff (2s, 4s, 8s, ...). 4xx other than 429 is not retried."""
    sess = session or requests
    last = None
    for attempt in range(retries + 1):
        try:
            r = sess.get(url, params=params, headers={**UA, **(headers or {})}, timeout=timeout)
            if r.status_code == 200:
                _store(r)
                return r
            last = f"HTTP {r.status_code}"
            if 400 <= r.status_code < 500 and r.status_code != 429:
                break
        except requests.RequestException as e:
            last = f"{type(e).__name__}: {e}"
        if attempt < retries:
            wait = backoff * (2 ** attempt)
            log.warning("GET %s failed (%s); retry %d/%d in %.0fs", url, last, attempt + 1, retries, wait)
            time.sleep(wait)
    raise FetchError(f"GET {url} failed: {last}")


def _store(r: requests.Response) -> None:
    """Keep the latest copy of each raw download plus a sidecar with when/what."""
    CACHE_DIR.mkdir(exist_ok=True)
    url = r.url
    for k in ("apiKey", "apikey"):
        url = re.sub(rf"{k}=[^&]+", f"{k}=***", url)
    base = CACHE_DIR / _cache_name(url)
    base.with_suffix(".raw").write_bytes(r.content)
    base.with_suffix(".meta.json").write_text(json.dumps({
        "url": url,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": r.status_code,
        "last_modified": r.headers.get("Last-Modified"),
        "bytes": len(r.content),
    }, indent=1))
