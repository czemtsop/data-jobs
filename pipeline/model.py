"""Write the star schema Power BI loads (one fact table, four dimensions)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .transform import PROVINCES

FACT_COLUMNS = [
    "posting_id", "posted_date", "province_code", "city", "title", "role_family", "seniority",
    "noc_code", "work_arrangement", "employment_type", "employment_term", "vacancies",
    "salary_min_annual", "salary_max_annual", "salary_mid_annual", "salary_period", "has_salary",
    "source_file",
]


def build_model(df: pd.DataFrame, model_dir: Path) -> dict[str, Path]:
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

    tables = {"fact_postings": fact, "dim_province": dim_province, "dim_role_family": dim_role,
              "dim_seniority": dim_seniority, "dim_date": dim_date}
    paths = {}
    for name, table in tables.items():
        p = model_dir / f"{name}.csv"
        table.to_csv(p, index=False, date_format="%Y-%m-%d")
        paths[name] = p
    return paths
