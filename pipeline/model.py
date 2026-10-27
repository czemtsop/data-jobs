"""Write the star schema Power BI loads (one fact table, four dimensions)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .transform import PROVINCES

FACT_COLUMNS = [
    "posting_id", "posted_date", "province_code", "city", "title", "role_family", "seniority",
    "noc_code", "noc_name", "data_source", "posting_source", "work_arrangement", "economic_region", "hours_per_week", "employment_type", "employment_term", "vacancies",
    "salary_min_annual", "salary_max_annual", "salary_mid_annual", "salary_period", "has_salary",
    "source_file", "posting_url",
]


def build_model(df: pd.DataFrame, model_dir: Path, skills: pd.DataFrame | None = None) -> dict[str, Path]:
    model_dir.mkdir(parents=True, exist_ok=True)
    fact = df[FACT_COLUMNS].copy()
    for c in ["salary_min_annual", "salary_max_annual", "salary_mid_annual"]:
        fact[c] = fact[c].round(0)

    dim_province = pd.DataFrame(
        [(code, name, region) for code, (name, region) in PROVINCES.items()],
        columns=["province_code", "province_name", "region"],
    )

    families = sorted(df["role_family"].unique())
    dim_role = pd.DataFrame({"role_family": families})
    dim_role["sort_order"] = dim_role["role_family"].eq("Other analyst").astype(int)

    dim_seniority = pd.DataFrame({"seniority": ["Junior", "Mid", "Senior", "Manager"], "sort_order": [1, 2, 3, 4]})

    start, end = df["posted_date"].min(), df["posted_date"].max()
    dates = pd.date_range(start.to_period("M").start_time, end.to_period("M").end_time, freq="D")
    dim_date = pd.DataFrame({"date": dates})
    dim_date["year"] = dim_date["date"].dt.year
    dim_date["month_num"] = dim_date["date"].dt.month
    dim_date["month"] = dim_date["date"].dt.strftime("%b %Y")
    dim_date["month_start"] = dim_date["date"].dt.to_period("M").dt.start_time
    dim_date["week_start"] = dim_date["date"] - pd.to_timedelta(dim_date["date"].dt.weekday, unit="D")

    # bridge table: one row per (posting, tool) — only live-scraped postings have these
    bridge = (skills if skills is not None else pd.DataFrame(columns=["posting_id", "skill"]))[["posting_id", "skill"]]
    dim_skill = bridge.groupby("skill").size().rename("postings").reset_index().sort_values("postings", ascending=False)

    tables = {"fact_postings": fact, "dim_province": dim_province, "dim_role_family": dim_role,
              "dim_seniority": dim_seniority, "dim_date": dim_date,
              "bridge_posting_skill": bridge, "dim_skill": dim_skill}
    paths = {}
    for name, table in tables.items():
        p = model_dir / f"{name}.csv"
        table.to_csv(p, index=False, date_format="%Y-%m-%d", encoding="utf-8-sig")  # BOM so Power BI reads accents
        paths[name] = p
    return paths
