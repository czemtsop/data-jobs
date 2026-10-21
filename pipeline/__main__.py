"""Command line entry point.

    python -m pipeline inspect   # show how each raw file's headers were mapped
    python -m pipeline run       # raw CSVs -> data/model/*.csv + findings -> README
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from . import findings, load, model, transform

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m pipeline")
    parser.add_argument("command", choices=["inspect", "run"])
    parser.add_argument("--config", default=ROOT / "config" / "config.yaml", type=Path)
    parser.add_argument("--no-readme", action="store_true", help="don't rewrite the README findings block")
    args = parser.parse_args()

    cfg = yaml.safe_load(args.config.read_text())
    raw_dir = ROOT / cfg["source"]["raw_dir"]
    pattern = cfg["source"]["file_glob"]

    if args.command == "inspect":
        print(load.inspect(raw_dir, pattern))
        return

    raw = load.load_all(raw_dir, pattern)
    print(f"Loaded {len(raw):,} postings from {raw['source_file'].nunique()} file(s)")
    df = transform.transform(raw, cfg)
    print(f"Kept {len(df):,} Canadian analyst postings")
    paths = model.build_model(df, ROOT / cfg["output"]["model_dir"])
    for name, p in paths.items():
        print(f"  wrote {p.relative_to(ROOT)}")
    f = findings.compute(df, cfg["findings"]["min_group_size"])
    md = findings.write(f, ROOT / cfg["output"]["findings_file"], None if args.no_readme else ROOT / "README.md")
    print("\nFindings:\n" + md)


if __name__ == "__main__":
    main()
