"""Append-only store of scraped postings.

Two CSVs under data/scraped/:
  postings.csv  one row per Job Bank job number (latest scrape wins)
  skills.csv    one row per (job_number, skill) from "Computer and technology knowledge"
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

POSTING_COLUMNS = [
    "job_number", "url", "title", "employer", "city", "province", "posted_date", "work_arrangement",
    "salary_min", "salary_max", "salary_per", "salary_text", "hours_min", "hours_max", "hours_per",
    "education", "experience", "noc_code", "source", "n_skills", "scraped_on",
]


def load(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype={"job_number": str, "noc_code": str}) if path.exists() else pd.DataFrame()


def known_ids(store_dir: Path) -> set[str]:
    df = load(store_dir / "postings.csv")
    return set(df["job_number"]) if len(df) else set()


def save(records: list[dict], store_dir: Path) -> tuple[int, int]:
    """Merge new records into the store; returns (postings now stored, skill rows now stored)."""
    store_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    rows, skill_rows = [], []
    for r in records:
        rows.append({**{c: r.get(c) for c in POSTING_COLUMNS}, "n_skills": len(r.get("skills") or []), "scraped_on": today})
        skill_rows += [{"job_number": r["job_number"], "skill": s} for s in dict.fromkeys(r.get("skills") or [])]

    p_path, s_path = store_dir / "postings.csv", store_dir / "skills.csv"
    new_ids = {r["job_number"] for r in records}
    postings = pd.concat([load(p_path), pd.DataFrame(rows, columns=POSTING_COLUMNS)], ignore_index=True)
    postings = postings.drop_duplicates("job_number", keep="last").sort_values(["posted_date", "job_number"])
    old_skills = load(s_path)
    if len(old_skills):
        old_skills = old_skills[~old_skills["job_number"].isin(new_ids)]
    skills = pd.concat([old_skills, pd.DataFrame(skill_rows, columns=["job_number", "skill"])], ignore_index=True)
    postings.to_csv(p_path, index=False)
    skills.to_csv(s_path, index=False)
    return len(postings), len(skills)
