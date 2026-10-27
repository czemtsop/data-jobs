"""Compute the headline numbers and write them into the README.

Every number in the README's Findings section comes from here, so rerunning
the pipeline on new months refreshes the README instead of leaving stale claims.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from .transform import PROVINCES

START, END = "<!-- FINDINGS:START -->", "<!-- FINDINGS:END -->"


def _median(s: pd.Series) -> float | None:
    s = s.dropna()
    return float(s.median()) if len(s) else None


def _money(x: float | None) -> str:
    return "n/a" if x is None else f"${x/1000:,.0f}K"


def _prov(code: str) -> str:
    return PROVINCES.get(code, (code,))[0]


def _pct(x: float) -> str:
    return f"{x:.0%}"


def _live_summary(live: pd.DataFrame, skills: pd.DataFrame | None) -> dict:
    if live.empty:
        return {"postings": 0}
    out = {
        "postings": int(len(live)),
        "first_date": live["posted_date"].min().strftime("%Y-%m-%d"),
        "last_date": live["posted_date"].max().strftime("%Y-%m-%d"),
        "work_arrangement_share": {k: float(v) for k, v in live["work_arrangement"].value_counts(normalize=True).items()},
    }
    if skills is not None and len(skills):
        sk = skills[skills["posting_id"].isin(live["posting_id"])]
        with_tools = sk["posting_id"].nunique()
        out["postings_listing_tools"] = int(with_tools)
        if with_tools:
            share = sk.groupby("skill")["posting_id"].nunique().sort_values(ascending=False) / with_tools
            out["tool_share"] = {k: float(v) for k, v in share.head(15).items()}
    return out


def _yearly(open_df: pd.DataFrame, all_monthly: dict[str, int], min_n: int) -> dict:
    """Same calendar window in every year (Jan to the latest complete month), open data only.

    Salary coverage changed a lot between years (partner postings rarely listed pay
    before mid-2025; every posting has since Dec 2025), so the like-for-like pay
    trend uses postings made directly on Job Bank, which always list a salary.
    """
    if open_df.empty:
        return {}
    last = open_df["posted_date"].max().to_period("M")
    window = open_df[open_df["posted_date"].dt.month <= last.month]
    out = {}
    for year, d in window.groupby(window["posted_date"].dt.year):
        months = [f"{year}-{m:02d}" for m in range(1, last.month + 1)]
        if d["posted_date"].dt.to_period("M").nunique() < last.month:
            continue                                  # incomplete year: not comparable
        direct = d[(d["posting_source"] == "Job Bank direct") & d["has_salary"]]["salary_mid_annual"]
        all_n = sum(all_monthly.get(m, 0) for m in months)
        out[int(year)] = {
            "postings": int(len(d)),
            "all_postings": int(all_n) if all(m in all_monthly for m in months) else None,
            "salary_coverage": float(d["has_salary"].mean()),
            "median_salary": _median(d.loc[d["has_salary"], "salary_mid_annual"]),
            "direct_median_salary": _median(direct) if len(direct) >= min_n else None,
            "direct_salaried": int(len(direct)),
            "role_family_share": {k: float(v) for k, v in d["role_family"].value_counts(normalize=True).items()},
        }
    return {"window": f"{pd.Period(f'{last.year}-01').strftime('%b')}–{last.strftime('%b')}", "years": out}


def compute(df: pd.DataFrame, min_n: int, all_monthly: dict[str, int] | None = None,
            skills: pd.DataFrame | None = None) -> dict:
    open_df = df[df["data_source"] == "Open data"]
    live = df[df["data_source"] == "Live scrape"]
    # pay rankings use the latest year only: earlier years have too few salaried postings to be representative
    pay_year = int(df["posted_date"].max().year)
    latest = df[df["posted_date"].dt.year == pay_year]
    sal = latest[latest["has_salary"]]

    prov = latest["province_code"].value_counts()
    family = df["role_family"].value_counts()

    def ranked(col: str) -> pd.DataFrame:
        g = sal.groupby(col)["salary_mid_annual"].agg(["median", "count"])
        return g[g["count"] >= min_n].sort_values("median", ascending=False)

    fam_pay, prov_pay, sen_pay = ranked("role_family"), ranked("province_code"), ranked("seniority")

    return {
        "scope": {
            "postings": int(len(df)),
            "vacancies": int(df["vacancies"].sum()),
            "first_date": df["posted_date"].min().strftime("%Y-%m-%d"),
            "last_date": df["posted_date"].max().strftime("%Y-%m-%d"),
            "months": int(df["posted_date"].dt.to_period("M").nunique()),
            "source_files": sorted(df["source_file"].unique().tolist()),
            "min_group_size": min_n,
        },
        "salary_coverage": float(df["has_salary"].mean()),
        "pay_year": pay_year,
        "pay_year_salary_coverage": float(latest["has_salary"].mean()),
        "national_median_salary": _median(sal["salary_mid_annual"]),
        "province_share": {k: float(v / len(latest)) for k, v in prov.items()},
        "role_family_share": {k: float(v / len(df)) for k, v in family.items()},
        "role_family_median": {k: {"median": float(r["median"]), "n": int(r["count"])} for k, r in fam_pay.iterrows()},
        "province_median": {k: {"median": float(r["median"]), "n": int(r["count"])} for k, r in prov_pay.iterrows()},
        "seniority_median": {k: {"median": float(r["median"]), "n": int(r["count"])} for k, r in sen_pay.iterrows()},
        "yearly": _yearly(open_df, all_monthly or {}, min_n),
        # trend uses complete open-data months only; the live scrape covers a partial month
        "monthly_postings": {str(k): int(v) for k, v in open_df.groupby(open_df["posted_date"].dt.to_period("M")).size().items()},
        "live_scrape": _live_summary(live, skills),
        "all_postings_monthly": all_monthly or {},
        "posting_source_share": {k: float(v) for k, v in df["posting_source"].value_counts(normalize=True).items()},
    }


def _change(a: float, b: float) -> str:
    """'fell 72%' / 'rose 5%' / 'was flat' for a -> b."""
    c = b / a - 1
    return "was flat" if abs(c) < 0.005 else f"{'rose' if c > 0 else 'fell'} {abs(c):.0%}"


def _trend_lines(f: dict) -> list[str]:
    """Year-over-year findings when at least two comparable years exist."""
    yr = f.get("yearly", {}).get("years", {})
    if len(yr) < 2:
        return []
    w = f["yearly"]["window"]
    (y0, a), (y1, b) = min(yr.items()), max(yr.items())
    lines = []

    # demand
    text = (f"**Analyst demand {'shrank' if b['postings'] < a['postings'] else 'grew'}.** {w} analyst postings "
            f"{_change(a['postings'], b['postings'])}, from {a['postings']:,} in {y0} to {b['postings']:,} in {y1}")
    if a["all_postings"] and b["all_postings"]:
        s0, s1 = a["postings"] / a["all_postings"], b["postings"] / b["all_postings"]
        text += (f", while all Job Bank postings {_change(a['all_postings'], b['all_postings'])}; analysts went from "
                 f"{s0:.1%} to {s1:.1%} of all postings")
    lines.append(text + ".")

    # pay, like for like
    if a["direct_median_salary"] and b["direct_median_salary"]:
        text = (f"**Advertised pay {'was flat' if abs(b['direct_median_salary'] / a['direct_median_salary'] - 1) < 0.05 else 'moved'}.** "
                f"Postings made directly on Job Bank, which always list a salary, had a median of "
                f"{_money(a['direct_median_salary'])} in {w} {y0} and {_money(b['direct_median_salary'])} in {y1} "
                f"(n={a['direct_salaried']:,} and {b['direct_salaried']:,})")
        if a["median_salary"] and b["median_salary"]:
            text += (f". The median across all postings {_change(a['median_salary'], b['median_salary'])}, but mostly "
                     f"because the share listing a salary went from {_pct(a['salary_coverage'])} to {_pct(b['salary_coverage'])}")
        lines.append(text + ".")

    # mix
    fa, fb = a["role_family_share"], b["role_family_share"]
    top = max(fb, key=fb.get)
    if "Data & BI" in fa and "Data & BI" in fb and top != "Data & BI":
        lines.append(f"**The mix moved toward data roles.** Data & BI went from {_pct(fa['Data & BI'])} of analyst "
                     f"postings in {y0} to {_pct(fb['Data & BI'])} in {y1}; {top} analysts are still the largest group "
                     f"at {_pct(fb[top])}.")
    return lines


def to_markdown(f: dict) -> str:
    sc = f["scope"]
    prov = list(f["province_share"].items())
    fam = list(f["role_family_share"].items())
    lines = _trend_lines(f)
    multi_year = bool(lines)

    if not multi_year:
        # 1. where demand is
        if len(prov) >= 2:
            (c1, s1), (c2, s2) = prov[0], prov[1]
            lines.append(f"**Demand is concentrated.** {_prov(c1)} and {_prov(c2)} account for {_pct(s1 + s2)} of the "
                         f"{sc['postings']:,} analyst postings ({_prov(c1)} alone {_pct(s1)}).")

        # 2. direction of travel within the year: first three months vs last three
        monthly = list(f["monthly_postings"].values())
        if len(monthly) >= 6:
            early, late = sum(monthly[:3]) / 3, sum(monthly[-3:]) / 3
            months = [pd.Period(m).strftime("%b") for m in f["monthly_postings"]]
            year = pd.Period(list(f["monthly_postings"])[-1]).year
            direction = "fell" if late < early else "rose"
            context = ""
            allm = list(f["all_postings_monthly"].values())
            if len(allm) == len(monthly):
                change = (sum(allm[-3:]) / sum(allm[:3])) - 1
                context = (f", while all Job Bank postings {'rose' if change > 0 else 'fell'} {abs(change):.0%} over the same period"
                           if abs(change) >= 0.005 else ", while all Job Bank postings were flat")
            lines.append(f"**Analyst hiring {'cooled' if late < early else 'picked up'}.** Monthly analyst postings {direction} "
                         f"{_pct(abs(late / early - 1))}, from an average of {early:,.0f} in {months[0]}–{months[2]} "
                         f"to {late:,.0f} in {months[-3]}–{months[-1]} {year}{context}.")

        # 3. what kind of analyst
        if fam:
            top_fam, top_share = fam[0]
            data_share = f["role_family_share"].get("Data & BI")
            extra = (f"; Data & BI roles are {_pct(data_share)}" if data_share is not None and top_fam != "Data & BI" else "")
            lines.append(f"**{top_fam} analysts are the largest group** at {_pct(top_share)} of postings{extra}.")

    py = f" in {f['pay_year']}" if multi_year else ""

    # pay by kind of analyst
    fm = f["role_family_median"]
    if len(fm) >= 2:
        (hi, h), (lo, l) = list(fm.items())[0], list(fm.items())[-1]
        lines.append(f"**The kind of analyst matters for pay.** {hi} postings{py} advertise a median {_money(h['median'])} "
                     f"(n={h['n']:,}), {_pct(h['median'] / l['median'] - 1)} more than {lo} at {_money(l['median'])} "
                     f"(n={l['n']:,}).")

    # pay in the two biggest markets
    pm = f["province_median"]
    if len(prov) >= 2 and prov[0][0] in pm and prov[1][0] in pm:
        a, b = prov[0][0], prov[1][0]
        ma, mb = pm[a]["median"], pm[b]["median"]
        hi_p, lo_p, hi_m, lo_m = (a, b, ma, mb) if ma >= mb else (b, a, mb, ma)
        lines.append(f"**Pay differs between the two biggest markets.** The median{py} is "
                     f"{_money(hi_m)} in {_prov(hi_p)} versus {_money(lo_m)} in {_prov(lo_p)}, "
                     f"{_pct(1 - lo_m / hi_m)} lower (national median {_money(f['national_median_salary'])}).")

    # tools asked for (live scrape only; needs enough postings that list tools)
    lv = f.get("live_scrape", {})
    n_tools = lv.get("postings_listing_tools", 0)
    if n_tools >= sc["min_group_size"] and lv.get("tool_share"):
        top = list(lv["tool_share"].items())[:3]
        tools = ", ".join(f"{k} ({_pct(v)})" for k, v in top)
        lines.insert(3, f"**The tools employers name.** Among {n_tools:,} recent postings that list computer skills "
                        f"({lv['first_date']} to {lv['last_date']}, scraped from jobbank.gc.ca), the most requested are {tools}.")
        lines = [l for l in lines if not l.startswith(f"**{fam[0][0]} analysts are the largest group")] if fam else lines

    numbered = "\n".join(f"{i}. {line}" for i, line in enumerate(lines[:5], 1))
    live_note = (f" Includes {lv['postings']:,} postings scraped from jobbank.gc.ca after the latest monthly file."
                 if lv.get("postings") else "")
    if multi_year:
        pay_note = (f"Year-over-year comparisons use the same months ({f['yearly']['window']}) in each year. Pay rankings "
                    f"use {f['pay_year']} only, when {_pct(f['pay_year_salary_coverage'])} of postings list a salary "
                    f"({_pct(f['salary_coverage'])} across the whole period).")
    else:
        pay_note = f"{_pct(f['salary_coverage'])} of postings include one."
    footer = (f"\n\n<sub>Job Bank postings with an analyst title, first posted {sc['first_date']} to {sc['last_date']} "
              f"({sc['months']} months).{live_note} Salaries are advertised ranges converted to annual CAD (midpoint). "
              f"{pay_note} Medians are only compared for groups with at least {sc['min_group_size']} salaried postings.</sub>")
    return numbered + footer


def write(f: dict, json_path: Path, readme: Path | None) -> str:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(f, indent=2))
    md = to_markdown(f)
    if readme and readme.exists():
        text = readme.read_text()
        if START in text and END in text:
            text = re.sub(re.escape(START) + r".*?" + re.escape(END), f"{START}\n{md}\n{END}", text, flags=re.S)
            readme.write_text(text)
    return md
