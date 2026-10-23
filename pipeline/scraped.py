"""Bring scraped postings (data/scraped/) into the same canonical schema as the open data.

Open-data files and the live site use different IDs (snapshot ID vs job number), so
the two can't be matched row by row. To avoid double counting, only scraped postings
first posted *after* the last open-data date are kept. When a new monthly file is
published, those weeks switch over to the open data automatically.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

SKILL_ALIASES = {
    "ms excel": "Excel", "microsoft excel": "Excel", "excel": "Excel",
    "power bi": "Power BI", "powerbi": "Power BI", "microsoft power bi": "Power BI",
    "sql": "SQL", "structured query language (sql)": "SQL", "ms sql server": "SQL Server", "sql server": "SQL Server",
    "python": "Python", "r": "R", "tableau": "Tableau", "sas": "SAS", "spss": "SPSS",
    "ms access": "Access", "ms office": "MS Office", "microsoft office": "MS Office",
    "sap": "SAP", "oracle": "Oracle", "salesforce": "Salesforce", "jira": "Jira",
}


def normalize_skill(s: str) -> str:
    key = s.strip().lower()
    return SKILL_ALIASES.get(key, s.strip())


def load_scraped(store_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    p, s = store_dir / "postings.csv", store_dir / "skills.csv"
    if not p.exists():
        return pd.DataFrame(), pd.DataFrame(columns=["posting_id", "skill"])
    d = pd.read_csv(p, dtype=str)
    raw = pd.DataFrame({
        "posting_id": "JB-" + d["job_number"],
        "original_title": d["title"],
        # older store files have no standard_title column; fall back to the posted title
        "title": d["standard_title"].fillna(d["title"]) if "standard_title" in d else d["title"],
        "noc_code": d["noc_code"],
        "province": d["province"],
        "city": d["city"],
        "posted_date": d["posted_date"],
        "salary_min": d["salary_min"],
        "salary_max": d["salary_max"],
        "salary_per": d["salary_per"],
        "hours_min": d["hours_min"],
        "hours_max": d["hours_max"],
        "hours_per": d["hours_per"],
        "external": d["source"].fillna("").str.contains("Job Bank", case=False).map({True: "0", False: "1"}),
        "work_arrangement": d["work_arrangement"],
        "source_file": "jobbank.gc.ca scrape",
    })
    skills = pd.read_csv(s, dtype=str) if s.exists() else pd.DataFrame(columns=["job_number", "skill"])
    skills = pd.DataFrame({"posting_id": "JB-" + skills["job_number"], "skill": skills["skill"].map(normalize_skill)})
    return raw, skills.drop_duplicates()


def after_open_data(scraped: pd.DataFrame, open_data_max: pd.Timestamp) -> pd.DataFrame:
    if scraped.empty:
        return scraped
    posted = pd.to_datetime(scraped["posted_date"], errors="coerce")
    return scraped[posted > open_data_max]
