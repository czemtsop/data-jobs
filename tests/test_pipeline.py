"""Tests run on a tiny synthetic file — these rows are made up and only exercise the code."""

from pathlib import Path

import pandas as pd
import pytest
import yaml

from pipeline import findings, load, model, transform

ROOT = Path(__file__).resolve().parent.parent
CFG = yaml.safe_load((ROOT / "config" / "config.yaml").read_text())

ROWS = [
    # id, title, province, city, date, min, max, per, hours, vacancies
    ("1", "Senior Data Analyst", "Ontario", "Toronto", "2026-09-02", "90000", "110000", "Year", "", "1"),
    ("2", "Junior Financial Analyst", "QC", "Montréal", "2026-09-03", "28", "32", "Hour", "40", "2"),
    ("3", "Business Systems Analyst", "Alberta", "Calgary", "2026-09-04", "6500", "7500", "Month", "", "1"),
    ("4", "Psychoanalyst", "Ontario", "Ottawa", "2026-09-05", "100000", "120000", "Year", "", "1"),
    ("5", "Software Developer", "Ontario", "Toronto", "2026-09-05", "90000", "100000", "Year", "", "1"),
    ("6", "Laboratory Analyst", "Saskatchewan", "Saskatoon", "2026-09-06", "", "", "", "", "1"),
    ("7", "BI Analyst", "British Columbia", "Vancouver", "2026-09-07", "1800", "2000", "Bi-weekly", "", "1"),
    ("7", "BI Analyst", "British Columbia", "Vancouver", "2026-09-07", "1800", "2000", "Bi-weekly", "", "1"),
    ("8", "Data Analyst", "Texas", "Austin", "2026-09-08", "70000", "80000", "Year", "", "1"),
]
HEADERS = ["WIC Job Location Snapshot ID", "Job Title", "Province/Territory", "City", "First Posting Date",
           "Salary Minimum", "Salary Maximum", "Salary Per", "Hours Minimum", "Vacancy Count"]


@pytest.fixture
def raw(tmp_path):
    p = tmp_path / "sample.csv"
    df = pd.DataFrame(ROWS, columns=HEADERS)
    df["Hours Maximum"] = df["Hours Minimum"]
    df["Hours Per"] = "Week"
    # external posting whose auto-assigned standard title is wrong: employer title must win
    df["Original Job Title"] = ""
    df.loc[len(df)] = ["9", "information technology (IT) analyst", "Ontario", "Toronto", "2026-09-09",
                       "60000", "60000", "Year", "", "1", "", "Week", "Business Strategy Specialist"]
    df.to_csv(p, index=False, encoding="utf-16", sep="\t")
    return load.load_month(p)


def test_headers_map(raw):
    assert {"posting_id", "title", "province", "salary_per"} <= set(raw.columns)


def test_filter_dedupe_and_derive(raw):
    df = transform.transform(raw, CFG).set_index("posting_id")
    assert set(df.index) == {"1", "2", "3", "6", "7"}   # psychoanalyst, developer, Texas, dupe, mis-coded title gone
    assert df.loc["1", "seniority"] == "Senior" and df.loc["2", "seniority"] == "Junior"
    assert df.loc["1", "role_family"] == "Data & BI"
    assert df.loc["2", "role_family"] == "Financial"
    assert df.loc["3", "role_family"] == "Business & Systems"
    assert df.loc["6", "role_family"] == "Lab & Quality"
    assert df.loc["2", "salary_mid_annual"] == pytest.approx(30 * 40 * 52)
    assert df.loc["3", "salary_mid_annual"] == pytest.approx(7000 * 12)
    assert df.loc["7", "salary_mid_annual"] == pytest.approx(1900 * 26)
    assert not df.loc["6", "has_salary"]


def test_model_and_findings(raw, tmp_path):
    df = transform.transform(raw, CFG)
    paths = model.build_model(df, tmp_path / "model")
    assert len(pd.read_csv(paths["fact_postings"])) == 5
    f = findings.compute(df, min_n=1)
    md = findings.to_markdown(f)
    assert md.startswith("1. ") and "postings" in md


def test_year_over_year_findings():
    """Two comparable years switch the findings to year-over-year mode with like-for-like pay."""
    rows = []
    for year, n, direct_pay in [(2024, 40, 70000), (2025, 30, 72000)]:
        for i in range(n):
            for month in (1, 2):
                rows.append({
                    "posting_id": f"{year}-{month}-{i}", "posted_date": pd.Timestamp(f"{year}-{month:02d}-15"),
                    "data_source": "Open data", "province_code": "ON", "role_family": "Data & BI" if i % 4 == 0 else "Financial",
                    "seniority": "Mid", "vacancies": 1, "source_file": "x.csv", "has_salary": True,
                    "posting_source": "Job Bank direct", "salary_mid_annual": direct_pay,
                })
    df = pd.DataFrame(rows)
    f = findings.compute(df, min_n=30, all_monthly={"2024-01": 4000, "2024-02": 4000, "2025-01": 2000, "2025-02": 2000})
    yr = f["yearly"]["years"]
    assert f["yearly"]["window"] == "Jan–Feb"
    assert yr[2024]["postings"] == 80 and yr[2025]["postings"] == 60
    assert yr[2025]["direct_median_salary"] == 72000
    md = findings.to_markdown(f)
    assert "fell 25%, from 80 in 2024 to 60 in 2025" in md
    assert "all Job Bank postings fell 50%" in md
    assert "$70K in Jan–Feb 2024 and $72K in 2025" in md
