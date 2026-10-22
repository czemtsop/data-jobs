"""Filter to analyst postings and derive the fields the dashboard needs."""

from __future__ import annotations

import html
import re

import numpy as np
import pandas as pd

PROVINCES = {
    "AB": ("Alberta", "Prairies"), "BC": ("British Columbia", "West Coast"),
    "MB": ("Manitoba", "Prairies"), "NB": ("New Brunswick", "Atlantic"),
    "NL": ("Newfoundland and Labrador", "Atlantic"), "NS": ("Nova Scotia", "Atlantic"),
    "NT": ("Northwest Territories", "North"), "NU": ("Nunavut", "North"),
    "ON": ("Ontario", "Central"), "PE": ("Prince Edward Island", "Atlantic"),
    "QC": ("Quebec", "Central"), "SK": ("Saskatchewan", "Prairies"),
    "YT": ("Yukon", "North"),
}
_PROVINCE_LOOKUP = {code.lower(): code for code in PROVINCES}
_PROVINCE_LOOKUP.update({name.lower(): code for code, (name, _) in PROVINCES.items()})
_PROVINCE_LOOKUP.update({"québec": "QC", "yukon territory": "YT", "pei": "PE", "nfld": "NL",
                         "colombie-britannique": "BC", "nouveau-brunswick": "NB",
                         "nouvelle-écosse": "NS", "terre-neuve-et-labrador": "NL",
                         "île-du-prince-édouard": "PE", "territoires du nord-ouest": "NT"})

PERIOD_MULTIPLIER = {"year": 1, "annual": 1, "yearly": 1, "month": 12, "week": 52,
                     "biweekly": 26, "day": 260, "hour": None}  # hour handled with hours/week


def _compile(patterns):
    return re.compile("|".join(f"(?:{p})" for p in patterns), re.IGNORECASE)


def _first_match(series: pd.Series, groups: list[dict], default: str) -> pd.Series:
    result = pd.Series(default, index=series.index, dtype="object")
    unassigned = pd.Series(True, index=series.index)
    for group in groups:
        hit = series.str.contains(_compile(group["patterns"]), na=False) & unassigned
        result[hit] = group["name"]
        unassigned &= ~hit
    return result


def clean_title(title: pd.Series) -> pd.Series:
    t = title.fillna("").map(html.unescape)
    return t.str.replace(r"\s+", " ", regex=True).str.strip()


def province_code(raw: pd.Series) -> pd.Series:
    return raw.fillna("").str.strip().str.lower().map(_PROVINCE_LOOKUP)


def _to_number(s: pd.Series) -> pd.Series:
    cleaned = s.astype("string").str.replace(r"[^0-9.]", "", regex=True)
    return pd.to_numeric(cleaned, errors="coerce").astype("float64")


def _period(raw: pd.Series) -> pd.Series:
    r = raw.fillna("").str.lower().str.replace("-", "", regex=False)
    out = pd.Series(pd.NA, index=raw.index, dtype="object")
    for key in ["hour", "biweekly", "week", "month", "day", "year", "annual"]:
        fr = {"hour": "heure", "week": "semaine", "month": "mois", "day": "jour", "year": "année", "annual": "an"}.get(key)
        hit = out.isna() & (r.str.contains(key) | (r.str.contains(fr) if fr else False))
        out[hit] = key
    return out


def annualize(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    s = cfg["salary"]
    period = _period(df["salary_per"])
    hours = weekly_hours(df).fillna(s["default_hours_per_week"])
    mult = period.map(PERIOD_MULTIPLIER).astype("float")
    mult = mult.where(period != "hour", hours * s["weeks_per_year"])
    out = pd.DataFrame(index=df.index)
    for side in ("min", "max"):
        val = _to_number(df[f"salary_{side}"]) * mult
        out[f"salary_{side}_annual"] = val.where(val.between(s["annual_floor"], s["annual_ceiling"]))
    out["salary_min_annual"] = out["salary_min_annual"].fillna(out["salary_max_annual"])
    out["salary_max_annual"] = out["salary_max_annual"].fillna(out["salary_min_annual"])
    out["salary_mid_annual"] = out[["salary_min_annual", "salary_max_annual"]].mean(axis=1)
    out["salary_period"] = period
    out["has_salary"] = out["salary_mid_annual"].notna()
    return out


HOURS_DIVISOR = {"week": 1, "biweekly": 2, "month": 52 / 12, "year": 52}


def weekly_hours(df: pd.DataFrame) -> pd.Series:
    """Average of min/max hours, converted to a weekly figure; implausible values -> NaN."""
    hmin, hmax = _to_number(df["hours_min"]), _to_number(df["hours_max"])
    avg = pd.concat([hmin, hmax], axis=1).mean(axis=1)
    per = df["hours_per"].fillna("week").str.lower().str.replace("-", "", regex=False)
    weekly = avg / per.map(HOURS_DIVISOR).astype("float")
    return weekly.where(weekly.between(5, 80))


def transform(raw: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    df = raw.copy()
    # Employer's own title when Job Bank has it; otherwise the posted (standard) title.
    # The standard title is auto-assigned for external postings and is often wrong
    # (e.g. "Business Strategy Specialist" coded as "information technology (IT) analyst").
    df["standard_title"] = clean_title(df["title"])
    df["title"] = clean_title(df["original_title"].where(df["original_title"].notna(), df["title"]))
    df["title"] = df["title"].where(df["title"] != "", df["standard_title"])
    inc = _compile(cfg["filters"]["title_include"])
    exc = _compile(cfg["filters"]["title_exclude"])
    df = df[df["title"].str.contains(inc) & ~df["title"].str.contains(exc)].copy()

    df["province_code"] = province_code(df["province"])
    df = df[df["province_code"].notna()].copy()             # Canada only

    df["posted_date"] = pd.to_datetime(df["posted_date"], errors="coerce", format="mixed").dt.normalize()
    df = df[df["posted_date"].notna()].copy()

    if df["posting_id"].notna().any():
        df = df.drop_duplicates(subset=["posting_id"], keep="last")
    else:  # fall back to a content key
        df = df.drop_duplicates(subset=["title", "city", "province_code", "posted_date"], keep="last")
        df["posting_id"] = pd.NA
    df["posting_id"] = df["posting_id"].fillna(pd.Series(range(1, len(df) + 1), index=df.index).map(lambda i: f"row{i}"))

    df["role_family"] = _first_match(df["title"], cfg["role_families"], "Other analyst")
    df["seniority"] = _first_match(df["title"], cfg["seniority"], "Mid")
    df = df.join(annualize(df, cfg))
    df["vacancies"] = _to_number(df["vacancies"]).fillna(1).clip(lower=1).astype(int)
    df["hours_per_week"] = weekly_hours(df).round(1)
    df["posting_source"] = df["external"].map({"1": "External job board", "0": "Job Bank direct"}).fillna("Unknown")
    scraped = df["source_file"].eq("jobbank.gc.ca scrape")
    df["data_source"] = scraped.map({True: "Live scrape", False: "Open data"})
    # on-site / hybrid / remote is only on the live posting pages
    arrangement = df["work_arrangement"] if "work_arrangement" in df else pd.Series(pd.NA, index=df.index)
    df["work_arrangement"] = arrangement.where(scraped).fillna("Not captured")
    df["noc_code"] = df["noc_code"].astype("string").str.extract(r"(\d{4,5})", expand=False)
    df["city"] = df["city"].fillna("").str.strip().str.title().replace("", np.nan)
    return df.reset_index(drop=True)
