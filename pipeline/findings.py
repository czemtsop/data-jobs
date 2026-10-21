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


def compute(df: pd.DataFrame, min_n: int) -> dict:
    sal = df[df["has_salary"]]
    nat_median = _median(sal["salary_mid_annual"])

    prov = df["province_code"].value_counts()
    family = df["role_family"].value_counts()

    def ranked(col: str) -> pd.DataFrame:
        g = sal.groupby(col)["salary_mid_annual"].agg(["median", "count"])
        return g[g["count"] >= min_n].sort_values("median", ascending=False)

    fam_pay, prov_pay, sen_pay = ranked("role_family"), ranked("province_code"), ranked("seniority")
    stated = df[df["work_arrangement"] != "Not stated"]

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
        "work_arrangement_share_of_stated": (
            {k: float(v) for k, v in stated["work_arrangement"].value_counts(normalize=True).items()}
            if len(stated) else {}
        ),
        "work_arrangement_stated_n": int(len(stated)),
    }


def to_markdown(f: dict) -> str:
    sc = f["scope"]
    prov = list(f["province_share"].items())
    fam = list(f["role_family_share"].items())
    lines = []

    if len(prov) >= 2:
        (p1, s1), (p2, s2) = prov[0], prov[1]
        p1, p2 = _prov(p1), _prov(p2)
        lines.append(f"**Demand is concentrated.** {p1} and {p2} account for {_pct(s1 + s2)} of the "
                     f"{sc['postings']:,} analyst postings ({p1} {_pct(s1)}, {p2} {_pct(s2)}).")

    if fam:
        top_fam, top_share = fam[0]
        data_share = f["role_family_share"].get("Data & BI")
        extra = (f" Data & BI roles are {_pct(data_share)} of postings." if data_share is not None and top_fam != "Data & BI" else "")
        lines.append(f"**{top_fam} is the largest analyst family** at {_pct(top_share)} of postings.{extra}")

    fm = f["role_family_median"]
    if len(fm) >= 2:
        (hi, h), (lo, l) = list(fm.items())[0], list(fm.items())[-1]
        lines.append(f"**Pay depends on the kind of analyst.** Median advertised pay is {_money(h['median'])} for "
                     f"{hi} (n={h['n']:,}) versus {_money(l['median'])} for {lo} (n={l['n']:,}), "
                     f"a {_pct(h['median'] / l['median'] - 1)} gap.")

    sm = f["seniority_median"]
    if "Senior" in sm and "Junior" in sm:
        s, j = sm["Senior"], sm["Junior"]
        lines.append(f"**Seniority premium.** Senior-titled postings advertise a median {_money(s['median'])}, "
                     f"{_pct(s['median'] / j['median'] - 1)} above junior-titled ones ({_money(j['median'])}).")

    pm = f["province_median"]
    if pm and f["national_median_salary"]:
        top_p, t = next(iter(pm.items()))
        top_p = _prov(top_p)
        nat = f["national_median_salary"]
        lines.append(f"**Where it pays most.** {top_p} has the highest provincial median at {_money(t['median'])} "
                     f"(n={t['n']:,}), {_pct(t['median'] / nat - 1)} above the national median of {_money(nat)}. "
                     f"{_pct(f['salary_coverage'])} of postings list a usable salary.")

    numbered = "\n".join(f"{i}. {line}" for i, line in enumerate(lines[:5], 1))
    footer = (f"\n\n<sub>Job Bank postings with an analyst title, first posted {sc['first_date']} to {sc['last_date']} "
              f"({sc['months']} month{'s' if sc['months'] != 1 else ''}). Salaries are advertised ranges converted to "
              f"annual CAD (midpoint); groups with fewer than {sc['min_group_size']} salaried postings are not ranked.</sub>")
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
