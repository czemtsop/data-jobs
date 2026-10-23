"""Command line entry point.

    python -m pipeline download  # fetch missing monthly open-data CSVs from open.canada.ca
    python -m pipeline inspect   # show how each raw file's headers were mapped
    python -m pipeline run       # download missing months, then raw CSVs -> data/model/*.csv + findings -> README
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd
import yaml

from . import download, findings, load, model, scraped, transform

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m pipeline")
    parser.add_argument("command", choices=["download", "inspect", "run"])
    parser.add_argument("--config", default=ROOT / "config" / "config.yaml", type=Path)
    parser.add_argument("--no-download", action="store_true", help="use only the CSVs already in the raw folder")
    parser.add_argument("--no-readme", action="store_true", help="don't rewrite the README findings block")
    args = parser.parse_args()

    cfg = yaml.safe_load(args.config.read_text())
    raw_dir = ROOT / cfg["source"]["raw_dir"]
    pattern = cfg["source"]["file_glob"]

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    src = cfg["source"]
    first_month, last_month = str(src["first_month"]), src.get("last_month") and str(src["last_month"])
    if args.command == "download" or (args.command == "run" and not args.no_download):
        download.download(raw_dir, first_month, last_month)
        if args.command == "download":
            return

    if args.command == "inspect":
        print(load.inspect(raw_dir, pattern))
        return

    raw = load.load_all(raw_dir, pattern, first_month, last_month)
    print(f"Loaded {len(raw):,} postings from {raw['source_file'].nunique()} open-data file(s)")
    posted = pd.to_datetime(raw["posted_date"], errors="coerce", format="mixed")
    all_monthly = {str(k): int(v) for k, v in posted.dt.to_period("M").value_counts().sort_index().items()}

    live, skills = scraped.load_scraped(ROOT / cfg["scrape"]["store_dir"])
    live = scraped.after_open_data(live, posted.max())
    if len(live):
        print(f"Adding {len(live):,} scraped postings first posted after {posted.max():%Y-%m-%d}")
        raw = pd.concat([raw, live], ignore_index=True)

    df = transform.transform(raw, cfg)
    skills = skills[skills["posting_id"].isin(df["posting_id"])]
    print(f"Kept {len(df):,} Canadian analyst postings ({(df['data_source'] == 'Live scrape').sum():,} from the live scrape)")
    paths = model.build_model(df, ROOT / cfg["output"]["model_dir"], skills)
    for name, p in paths.items():
        print(f"  wrote {p.relative_to(ROOT)}")
    f = findings.compute(df, cfg["findings"]["min_group_size"], all_monthly, skills)
    md = findings.write(f, ROOT / cfg["output"]["findings_file"], None if args.no_readme else ROOT / "README.md")
    print("\nFindings:\n" + md)


if __name__ == "__main__":
    main()
