"""Download the monthly Job Bank open-data CSVs from open.canada.ca.

The files are public (Open Government Licence – Canada) and ~45 MB each, so they
aren't kept in git. The dataset's file list comes from the portal's CKAN API, so
a newly published month is picked up without code changes. Files already in the
raw folder are skipped.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import requests

log = logging.getLogger(__name__)

DATASET_ID = "ea639e28-c0fc-48bf-b5dd-b8899bd43072"
API = "https://open.canada.ca/data/api/action/package_show"
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
# file names are irregular: ...-en-sept2026.csv, ...-en-december2025.csv, ...-postings-aug2024.csv,
# june-2024-job-bank-open-data-all-job-postings-en.csv
MONTH_YEAR = re.compile(r"([a-z]+)[-\s]?(\d{4})", re.I)


def month_of(text: str) -> str | None:
    """First '<month name><year>' in a file or resource name -> 'YYYY-MM' ('sept2026' -> '2026-09')."""
    for m in MONTH_YEAR.finditer(text):
        word = m.group(1).lower()
        if word[:3] in MONTHS and len(word) <= 9:
            return f"{m.group(2)}-{MONTHS.index(word[:3]) + 1:02d}"
    return None


def available(session: requests.Session | None = None) -> dict[str, tuple[str, str]]:
    """{'2026-09': (file name, download URL), ...} for every English monthly file on the portal.

    Month and language come from the resource's metadata ("June 2024 Job Postings ...",
    language ['en']), since the file names don't follow one pattern.
    """
    r = (session or requests).get(API, params={"id": DATASET_ID}, timeout=60)
    r.raise_for_status()
    out = {}
    for res in r.json()["result"]["resources"]:
        name = res["url"].rsplit("/", 1)[-1]
        if "en" not in (res.get("language") or []) or not name.lower().endswith(".csv"):
            continue
        month = month_of(res.get("name") or "") or month_of(name)
        if month:
            out[month] = (name, res["url"])
    return dict(sorted(out.items()))


def in_range(month: str | None, first_month: str, last_month: str | None) -> bool:
    return month is not None and month >= first_month and (last_month is None or month <= last_month)


def download(raw_dir: Path, first_month: str, last_month: str | None = None) -> list[Path]:
    """Fetch missing months in [first_month, last_month] (YYYY-MM; open-ended if last_month is None)."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    wanted = {m: v for m, v in available(session).items() if in_range(m, first_month, last_month)}
    have = {month_of(p.name) for p in raw_dir.glob("*.csv")}
    fetched = []
    for month, (name, url) in wanted.items():
        if month in have:
            continue
        dest = raw_dir / name
        part = dest.with_suffix(".csv.part")
        log.info("downloading %s", name)
        with session.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with part.open("wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
        part.replace(dest)   # only a complete file gets the .csv name
        fetched.append(dest)
    log.info("%d open-data file(s) in %s (%d downloaded)", len(wanted), raw_dir, len(fetched))
    return fetched
