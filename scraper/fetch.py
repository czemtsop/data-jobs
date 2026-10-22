"""Polite HTTP client for jobbank.gc.ca.

robots.txt sets `Crawl-delay: 5`, so every request waits at least that long.
Responses can be saved to disk (--save-html) to replay or debug the parser.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from urllib.parse import urlencode

import requests

log = logging.getLogger(__name__)

BASE = "https://www.jobbank.gc.ca"
USER_AGENT = "data-jobs research scraper (+https://github.com/czemtsop/data-jobs)"


class JobBankClient:
    def __init__(self, delay: float = 5.0, save_dir: Path | None = None, timeout: float = 30.0):
        self.delay = max(delay, 5.0)
        self.save_dir = save_dir
        self.timeout = timeout
        self._last = 0.0
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-CA,en;q=0.8"})

    def _get(self, url: str, save_as: str | None = None, retries: int = 3) -> str:
        for attempt in range(1, retries + 1):
            wait = self.delay - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                r = self.session.get(url, timeout=self.timeout)
                if r.status_code == 429 or r.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {r.status_code}")
                r.raise_for_status()
                if self.save_dir and save_as:
                    self.save_dir.mkdir(parents=True, exist_ok=True)
                    (self.save_dir / save_as).write_bytes(r.content)
                return r.text
            except requests.RequestException as e:
                log.warning("attempt %d/%d failed for %s: %s", attempt, retries, url, e)
                time.sleep(self.delay * attempt * 2)
        raise RuntimeError(f"giving up on {url}")

    def search_page(self, query: str, page: int) -> str:
        params = {"searchstring": query, "sort": "D", "page": page}  # sort=D: newest first
        return self._get(f"{BASE}/jobsearch/jobsearch?{urlencode(params)}", f"search_{query}_p{page}.html")

    def posting(self, job_number: str) -> str:
        return self._get(f"{BASE}/jobsearch/jobposting/{job_number}", f"posting_{job_number}.html")
