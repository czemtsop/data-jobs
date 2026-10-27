"""Parser tests on real Job Bank pages saved on 2026-10-22 (`python -m scraper --save-html`).

- search_analyst.html: page 1 of a newest-first search for "analyst"
- posting_50559119_partner.html: copied from indeed.com, where Job Bank's standard
  title ("job analyst") differs from the employer's ("FP&A Analyst")
- posting_50559745_direct.html: posted directly on Job Bank, with the structured
  education / tasks / skills sections
"""

from pathlib import Path

from scraper import parse, store

FIX = Path(__file__).parent / "fixtures"


def _posting(name: str, job: str) -> dict:
    return parse.parse_posting((FIX / name).read_bytes(), job)


def test_search_ids():
    ids = parse.parse_search((FIX / "search_analyst.html").read_bytes())
    assert len(ids) == 25
    assert ids[:3] == ["50562109", "50561439", "50560585"]


def test_partner_posting_uses_employer_title():
    r = _posting("posting_50559119_partner.html", "50559119")
    assert r["title"] == "FP&A Analyst"
    assert r["standard_title"] == "job analyst"
    assert r["employer"] == "JAMESWAY INCUBATOR COMPANY"
    assert (r["city"], r["province"]) == ("Cambridge", "ON")
    assert r["posted_date"] == "2026-10-22"
    assert (r["salary_min"], r["salary_max"], r["salary_per"]) == (85000, 95000, "Year")
    assert r["salary_text"] == "$85,000 to $95,000 annually"
    assert r["work_arrangement"] == "On site"
    assert r["source"] == "indeed.com"
    assert r["noc_code"] == "11200"
    # partner postings carry no structured requirements; the description mentions "$" amounts
    # and hours that must not be picked up
    assert r["skills"] == [] and r["tasks"] == []
    assert r["hours_min"] is None


def test_direct_posting_fields():
    r = _posting("posting_50559745_direct.html", "50559745")
    assert r["title"] == r["standard_title"] == "business systems analyst"
    assert r["employer"] == "Metalogics"
    assert (r["city"], r["province"]) == ("Etobicoke", "ON")
    assert (r["salary_min"], r["salary_max"], r["salary_per"]) == (71000, 71000, "Year")
    assert (r["hours_min"], r["hours_max"], r["hours_per"]) == (30, 35, "Week")
    assert r["education"] == "Bachelor's degree"
    assert r["experience"] == "2 years to less than 3 years"
    assert r["skills"] == ["Zoho CRM"]
    assert len(r["tasks"]) == 7
    assert r["source"] == "Job Bank"
    assert r["noc_code"] == "21221"


def test_parse_quality_on_fixtures():
    records = [_posting("posting_50559119_partner.html", "1"), _posting("posting_50559745_direct.html", "2")]
    q = parse.parse_quality(records)
    assert all(q[f] == 1 for f in parse.CORE_FIELDS)
    assert q["skills"] == 0.5


def test_store_merges(tmp_path):
    r = _posting("posting_50559745_direct.html", "1")
    assert store.save([r], tmp_path) == (1, 1)
    r2 = {**r, "skills": ["SQL", "Python"]}
    assert store.save([r2], tmp_path) == (1, 2)     # re-scrape replaces, doesn't duplicate
    assert store.known_ids(tmp_path) == {"1"}


def test_search_dates():
    res = parse.parse_search_dates((FIX / "search_analyst.html").read_bytes())
    assert list(res) == parse.parse_search((FIX / "search_analyst.html").read_bytes())
    assert set(res.values()) == {"2026-10-22"}


def test_seen_ids_include_dropped_postings(tmp_path):
    store.save([_posting("posting_50559745_direct.html", "1")], tmp_path)
    store.mark_seen(["1", "7", "12"], tmp_path)
    store.mark_seen(["7"], tmp_path)
    assert store.known_ids(tmp_path) == {"1", "7", "12"}
    assert (tmp_path / store.SEEN_FILE).read_text() == "1\n7\n12\n"


def test_scrape_since(tmp_path):
    from datetime import date

    from scraper.__main__ import scrape_since

    for name in ["job-bank-open-data-all-job-postings-en-sept2026.csv",
                 "job-bank-open-data-all-job-postings-en-december2025.csv"]:
        (tmp_path / name).touch()
    assert scrape_since(tmp_path, "*.csv") == date(2026, 10, 1)
    (tmp_path / "job-bank-open-data-all-job-postings-en-december2026.csv").touch()
    assert scrape_since(tmp_path, "*.csv") == date(2027, 1, 1)
