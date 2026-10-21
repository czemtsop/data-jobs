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
    ("7", "BI Analyst (Remote)", "British Columbia", "Vancouver", "2026-09-07", "1800", "2000", "Bi-weekly", "", "1"),
    ("7", "BI Analyst (Remote)", "British Columbia", "Vancouver", "2026-09-07", "1800", "2000", "Bi-weekly", "", "1"),
    ("8", "Data Analyst", "Texas", "Austin", "2026-09-08", "70000", "80000", "Year", "", "1"),
]
HEADERS = ["Job Posting ID", "Job Title", "Province/Territory", "City", "First Posting Date",
           "Salary Minimum", "Salary Maximum", "Salary Per", "Work Hours", "Vacancy Count"]


@pytest.fixture
def raw(tmp_path):
    p = tmp_path / "sample.csv"
    pd.DataFrame(ROWS, columns=HEADERS).to_csv(p, index=False, encoding="utf-16", sep="\t")
    return load.load_month(p)


def test_headers_map(raw):
    assert {"posting_id", "title", "province", "salary_per"} <= set(raw.columns)


def test_filter_dedupe_and_derive(raw):
    df = transform.transform(raw, CFG).set_index("posting_id")
    assert set(df.index) == {"1", "2", "3", "6", "7"}           # psychoanalyst, developer, Texas, dupe gone
    assert df.loc["1", "seniority"] == "Senior" and df.loc["2", "seniority"] == "Junior"
    assert df.loc["1", "role_family"] == "Data & BI"
    assert df.loc["2", "role_family"] == "Financial"
    assert df.loc["3", "role_family"] == "Business & Systems"
    assert df.loc["6", "role_family"] == "Lab & Quality"
    assert df.loc["2", "salary_mid_annual"] == pytest.approx(30 * 40 * 52)
    assert df.loc["3", "salary_mid_annual"] == pytest.approx(7000 * 12)
    assert df.loc["7", "salary_mid_annual"] == pytest.approx(1900 * 26)
    assert df.loc["7", "work_arrangement"] == "Remote"
    assert not df.loc["6", "has_salary"]


def test_model_and_findings(raw, tmp_path):
    df = transform.transform(raw, CFG)
    paths = model.build_model(df, tmp_path / "model")
    assert len(pd.read_csv(paths["fact_postings"])) == 5
    f = findings.compute(df, min_n=1)
    md = findings.to_markdown(f)
    assert md.startswith("1. ") and "postings" in md
