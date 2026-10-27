"""Scrape current analyst postings from jobbank.gc.ca.

    python -m scraper                      # newest postings for each configured query
    python -m scraper --max-pages 2 --save-html data/scraped/html   # small run, keep raw pages
    python -m scraper --reparse data/scraped/html                   # re-run the parser on saved pages

New postings are merged into data/scraped/. Run `python -m pipeline run` afterwards
to rebuild the Power BI tables and README findings.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from datetime import date
from pathlib import Path

import yaml

from pipeline.download import month_of

from . import parse, store
from .fetch import JobBankClient

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("scraper")


def scrape_since(raw_dir: Path, file_glob: str) -> date:
    """First day after the latest downloaded open-data month; earlier postings are covered by the open data.

    With no open-data files on disk, falls back to the first day of last month
    (ESDC usually publishes a month's file a few weeks after it ends).
    """
    months = [m for m in (month_of(p.name) for p in raw_dir.glob(file_glob)) if m]
    if months:
        year, month = map(int, max(months).split("-"))
        return date(year + month // 12, month % 12 + 1, 1)
    today = date.today()
    log.warning("no open-data files in %s; collecting from the start of last month", raw_dir)
    return date(today.year - (today.month == 1), (today.month - 2) % 12 + 1, 1)


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m scraper")
    ap.add_argument("--config", type=Path, default=ROOT / "config" / "config.yaml")
    ap.add_argument("--max-pages", type=int, help="override scrape.max_pages_per_query")
    ap.add_argument("--save-html", type=Path, help="also save every fetched page here")
    ap.add_argument("--reparse", type=Path, help="parse saved posting_*.html files instead of fetching")
    ap.add_argument("--since", type=date.fromisoformat,
                    help="earliest posted date to collect (YYYY-MM-DD); default: the day after the open data ends")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    cfg = yaml.safe_load(args.config.read_text())
    sc = cfg["scrape"]
    store_dir = ROOT / sc["store_dir"]
    include = re.compile("|".join(cfg["filters"]["title_include"]), re.I)
    exclude = re.compile("|".join(cfg["filters"]["title_exclude"]), re.I)

    if args.reparse:
        records = [parse.parse_posting(p.read_bytes(), p.stem.split("_", 1)[1])
                   for p in sorted(args.reparse.glob("posting_*.html"))]
    else:
        client = JobBankClient(delay=sc["delay_seconds"], save_dir=args.save_html)
        seen = store.known_ids(store_dir)
        since = (args.since or scrape_since(ROOT / cfg["source"]["raw_dir"], cfg["source"]["file_glob"])).isoformat()
        log.info("collecting postings dated %s or later", since)
        max_pages = args.max_pages or sc["max_pages_per_query"]
        to_fetch: list[str] = []
        for query in sc["queries"]:
            for page in range(1, max_pages + 1):
                results = parse.parse_search_dates(client.search_page(query, page))
                fresh = [i for i, d in results.items()
                         if i not in seen and i not in to_fetch and (d is None or d >= since)]
                log.info("query=%r page=%d: %d postings, %d new", query, page, len(results), len(fresh))
                to_fetch += fresh
                dates = [d for d in results.values() if d]
                # Results are newest first, so stop at the cutoff date. Pages that are already
                # fully seen don't stop the crawl: a run cut short by max_postings_per_run
                # leaves older postings for the next run to pick up.
                if not results or (dates and min(dates) < since):
                    break
            else:
                log.warning("query=%r: hit max_pages_per_query (%d) before reaching %s", query, max_pages, since)
        to_fetch = to_fetch[: sc["max_postings_per_run"]]
        log.info("fetching %d posting pages (~%d min)", len(to_fetch), len(to_fetch) * client.delay // 60)
        records = []
        for n, job in enumerate(to_fetch, 1):
            try:
                records.append(parse.parse_posting(client.posting(job), job))
            except Exception as e:  # one bad page shouldn't lose the run
                log.warning("posting %s failed: %s", job, e)
            if n % 25 == 0:
                log.info("%d/%d", n, len(to_fetch))

    in_scope = [r for r in records if r["title"] and include.search(r["title"]) and not exclude.search(r["title"])]
    quality = parse.parse_quality(in_scope)
    log.info("parsed %d postings, %d with an analyst title", len(records), len(in_scope))
    log.info("field coverage: %s", {k: f"{v:.0%}" for k, v in quality.items()})
    if in_scope and quality["title"] < 0.9:
        log.error("fewer than 90%% of postings have a title: the page layout may have changed; not saving")
        sys.exit(1)
    n_post, n_skill = store.save(in_scope, store_dir)
    # remember dropped postings too; pages that failed or had no title are retried next run
    store.mark_seen([r["job_number"] for r in records if r["title"]], store_dir)
    log.info("store now holds %d postings and %d skill rows in %s", n_post, n_skill, store_dir.relative_to(ROOT))


if __name__ == "__main__":
    main()
