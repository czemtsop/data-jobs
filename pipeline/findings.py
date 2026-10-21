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


def compute(df: pd.DataFrame, min_n: int, all_monthly: dict[str, int] | None = None) -> dict:
    sal = df[df["has_salary"]]
    nat_median = _median(sal["salary_mid_annual"])

    prov = df["province_code"].value_counts()
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
        "national_median_salary": nat_median,
        "province_share": {k: float(v / len(df)) for k, v in prov.items()},
        "role_family_share": {k: float(v / len(df)) for k, v in family.items()},
        "role_family_median": {k: {"median": float(r["median"]), "n": int(r["count"])} for k, r in fam_pay.iterrows()},
        "province_median": {k: {"median": float(r["median"]), "n": int(r["count"])} for k, r in prov_pay.iterrows()},
        "seniority_median": {k: {"median": float(r["median"]), "n": int(r["count"])} for k, r in sen_pay.iterrows()},
        "monthly_postings": {str(k): int(v) for k, v in df.groupby(df["posted_date"].dt.to_period("M")).size().items()},
        "all_postings_monthly": all_monthly or {},
        "posting_source_share": {k: float(v) for k, v in df["posting_source"].value_counts(normalize=True).items()},
    }


def to_markdown(f: dict) -> str:
    sc = f["scope"]
    prov = list(f["province_share"].items())
    fam = list(f["role_family_share"].items())
    lines = []

    # 1. where demand is
    if len(prov) >= 2:
        (c1, s1), (c2, s2) = prov[0], prov[1]
        lines.append(f"**Demand is concentrated.** {_prov(c1)} and {_prov(c2)} account for {_pct(s1 + s2)} of the "
                     f"{sc['postings']:,} analyst postings ({_prov(c1)} alone {_pct(s1)}).")

    # 2. direction of travel: first three months vs last three
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

    # 4. pay by kind of analyst
    fm = f["role_family_median"]
    if len(fm) >= 2:
        (hi, h), (lo, l) = list(fm.items())[0], list(fm.items())[-1]
        lines.append(f"**The kind of analyst matters for pay.** {hi} postings advertise a median {_money(h['median'])} "
                     f"(n={h['n']:,}), {_pct(h['median'] / l['median'] - 1)} more than {lo} at {_money(l['median'])} "
                     f"(n={l['n']:,}).")

    # 5. pay in the two biggest markets
    pm = f["province_median"]
    if len(prov) >= 2 and prov[0][0] in pm and prov[1][0] in pm:
        a, b = prov[0][0], prov[1][0]
        ma, mb = pm[a]["median"], pm[b]["median"]
        hi_p, lo_p, hi_m, lo_m = (a, b, ma, mb) if ma >= mb else (b, a, mb, ma)
        lines.append(f"**Pay differs between the two biggest markets.** The median is "
                     f"{_money(hi_m)} in {_prov(hi_p)} versus {_money(lo_m)} in {_prov(lo_p)}, "
                     f"{_pct(1 - lo_m / hi_m)} lower (national median {_money(f['national_median_salary'])}).")

    numbered = "\n".join(f"{i}. {line}" for i, line in enumerate(lines[:5], 1))
    footer = (f"\n\n<sub>Job Bank postings with an analyst title, first posted {sc['first_date']} to {sc['last_date']} "
              f"({sc['months']} months). Salaries are advertised ranges converted to annual CAD (midpoint); "
              f"{_pct(f['salary_coverage'])} of postings include one. Medians are only compared for groups with at "
              f"least {sc['min_group_size']} salaried postings.</sub>")
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
