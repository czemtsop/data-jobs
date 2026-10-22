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
from pathlib import Path

import yaml

from . import parse, store
from .fetch import JobBankClient

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("scraper")


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m scraper")
    ap.add_argument("--config", type=Path, default=ROOT / "config" / "config.yaml")
    ap.add_argument("--max-pages", type=int, help="override scrape.max_pages_per_query")
    ap.add_argument("--save-html", type=Path, help="also save every fetched page here")
    ap.add_argument("--reparse", type=Path, help="parse saved posting_*.html files instead of fetching")
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
        max_pages = args.max_pages or sc["max_pages_per_query"]
        to_fetch: list[str] = []
        for query in sc["queries"]:
            for page in range(1, max_pages + 1):
                ids = parse.parse_search(client.search_page(query, page))
                fresh = [i for i in ids if i not in seen and i not in to_fetch]
                log.info("query=%r page=%d: %d postings, %d new", query, page, len(ids), len(fresh))
                to_fetch += fresh
                if not ids or not fresh:   # results are newest-first: an all-known page means we've caught up
                    break
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
    log.info("store now holds %d postings and %d skill rows in %s", n_post, n_skill, store_dir.relative_to(ROOT))


if __name__ == "__main__":
    main()
