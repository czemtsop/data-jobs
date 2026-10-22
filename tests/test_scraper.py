"""Parser tests on hand-built fixtures (see the comment at the top of each fixture)."""

from pathlib import Path

from scraper import parse, store

FIX = Path(__file__).parent / "fixtures"


def test_search_ids():
    assert parse.parse_search((FIX / "search_hand_built.html").read_text()) == ["50545586", "50516014"]


def test_posting_fields():
    r = parse.parse_posting((FIX / "posting_hand_built.html").read_text(), "50516014")
    assert r["title"] == "data analyst - informatics and systems"
    assert r["employer"] == "Example Analytics Inc."
    assert (r["city"], r["province"]) == ("Toronto", "ON")
    assert r["posted_date"] == "2026-10-16"
    assert (r["salary_min"], r["salary_max"], r["salary_per"]) == (85000, 95000, "Year")
    assert (r["hours_min"], r["hours_per"]) == (37.5, "Week")
    assert r["work_arrangement"] == "Hybrid"
    assert r["education"] == "Bachelor's degree"
    assert r["skills"] == ["SQL", "Python", "Power BI", "MS Excel"]
    assert len(r["tasks"]) == 2
    assert r["noc_code"] == "21223"


def test_store_merges(tmp_path):
    r = parse.parse_posting((FIX / "posting_hand_built.html").read_text(), "1")
    assert store.save([r], tmp_path) == (1, 4)
    r2 = {**r, "skills": ["SQL"]}
    assert store.save([r2], tmp_path) == (1, 1)     # re-scrape replaces, doesn't duplicate
    assert store.known_ids(tmp_path) == {"1"}
