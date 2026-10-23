"""Parse Job Bank pages with BeautifulSoup.

Fields are located by things a page has to keep to stay usable, not by CSS
class names:
  - schema.org `property` attributes (title, datePosted, hiringOrganization,
    addressLocality, baseSalary/minValue/maxValue/unitText, workHours), a
    published vocabulary that search engines read;
  - visible or screen-reader labels ("Work location", "Source",
    "Title posted on ... -");
  - section headings ("Education", "Tasks", "Computer and technology knowledge").

Every field is optional: a missing one gives None rather than an exception, and
`parse_quality` reports how many core fields were found so a silent layout
change shows up in the run log.

Most postings are copied from partner sites (indeed.com, Jobillico, ...). For
those, the <h1> is Job Bank's auto-assigned standard title, which is often wrong
(an "HVAC Sheet Metal Worker" shows up as a "testing, adjusting and balancing
technician"). The employer's own title is in the "Title posted on <site> - ..."
line, and that's what `title` holds. Partner postings also have no structured
skills or tasks lists; only postings made directly on Job Bank do.
"""

from __future__ import annotations

import re
from datetime import datetime

from bs4 import BeautifulSoup, Tag

POSTING_LINK = re.compile(r"/jobsearch/jobposting/(\d+)")
ORIGINAL_TITLE_LABEL = re.compile(r"^\s*Title posted on .+?\s-\s*$", re.I)

ARRANGEMENTS = [
    ("Remote", re.compile(r"\bremote\b|work must be completed remotely|télétravail", re.I)),
    ("Hybrid", re.compile(r"\bhybrid\b|both in person and remotely|hybride", re.I)),
    ("On site", re.compile(r"\bon site\b|work must be completed at the physical location|sur place", re.I)),
]

# schema.org unitText -> salary_per values used by pipeline/transform.py
SALARY_UNITS = [("BI", "Bi-weekly"), ("HOUR", "Hour"), ("YEAR", "Year"), ("ANNUAL", "Year"),
                ("MONTH", "Month"), ("WEEK", "Week"), ("DAY", "Day")]


def _soup(html: str | bytes) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def _clean(text: str | None) -> str | None:
    if text is None:
        return None
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _number(text: str | None) -> float | None:
    try:
        return float(text.replace(",", "").replace("$", "").strip()) if text else None
    except ValueError:
        return None


# ---------------------------------------------------------------- search pages

def parse_search(html: str | bytes) -> list[str]:
    """Posting IDs in page order, de-duplicated."""
    soup = _soup(html)
    ids = []
    for a in soup.find_all("a", href=True):
        m = POSTING_LINK.search(a["href"])
        if m and m.group(1) not in ids:
            ids.append(m.group(1))
    return ids


# ---------------------------------------------------------------- posting pages

def _prop(soup: BeautifulSoup | Tag, name: str) -> Tag | None:
    """First element whose RDFa `property` list includes `name`."""
    return soup.find(attrs={"property": lambda v: v and name in v.split()})


def _prop_text(soup: BeautifulSoup | Tag, name: str) -> str | None:
    el = _prop(soup, name)
    return _clean(el.get_text(" ")) if el else None


def _labelled(soup: BeautifulSoup, label: str) -> str | None:
    """Text of the value next to a screen-reader label, e.g. 'Work location' -> 'On site'."""
    for lab in soup.find_all(class_="wb-inv"):
        if _clean(lab.get_text()) == label:
            parts = [_clean(s.get_text(" ")) for s in lab.find_next_siblings(["span", "a"])]
            return _clean(" ".join(p for p in parts if p))
    return None


def _section(soup: BeautifulSoup, heading: str) -> list[str]:
    """Items under an <h3>/<h4> heading: <li> texts if it's a list, else the paragraph text."""
    for h in soup.find_all(["h3", "h4"]):
        if (_clean(h.get_text(" ")) or "").lower() != heading.lower():
            continue
        nxt = h.find_next_sibling()
        if not isinstance(nxt, Tag) or nxt.name in ("h3", "h4"):
            return []
        if nxt.name in ("ul", "ol"):
            items = [_clean(li.get_text(" ")) for li in nxt.find_all("li")]
        else:
            items = [_clean(nxt.get_text(" "))]
        return [p.strip() for x in items if x for p in x.split(";") if p.strip()]
    return []


def _title(soup: BeautifulSoup) -> tuple[str | None, str | None]:
    """(employer's title, Job Bank's standard title)."""
    h1 = soup.find("h1")
    standard = _clean((_prop(h1, "title") or h1).get_text(" ")) if h1 else None
    label = soup.find(string=ORIGINAL_TITLE_LABEL)
    if label:
        box = label.find_parent("p") or label.parent.parent
        original = _clean(box.get_text(" ").replace(str(label), "", 1))
        if original:
            return original, standard
    return standard, standard


def _salary(soup: BeautifulSoup) -> dict:
    out = {"salary_min": None, "salary_max": None, "salary_per": None, "salary_text": None}
    box = _prop(soup, "baseSalary")
    if not box:
        return out
    lo, hi = _prop(box, "minValue"), _prop(box, "maxValue")
    lo = _number(lo.get("content") or lo.get_text()) if lo else None
    hi = _number(hi.get("content") or hi.get_text()) if hi else None
    unit = (_prop_text(box, "unitText") or "").upper()
    # "$16.31 to $38.98 hourly": drop the machine-readable unit and the trailing "/ 30 hours per week"
    visible = " ".join(s for s in box.find_all(string=True)
                       if not s.find_parent(attrs={"property": ["unitText", "workHours"]}))
    visible = re.sub(r"\$\s+", "$", _clean(visible) or "")
    out.update(
        salary_min=lo,
        salary_max=hi if hi is not None else lo,
        salary_per=next((p for k, p in SALARY_UNITS if k in unit), None),
        salary_text=_clean(re.sub(r"\s*/\s*$", "", visible)),
    )
    return out


def _hours(soup: BeautifulSoup) -> dict:
    text = _prop_text(soup, "workHours")
    m = re.search(r"([\d.]+)(?:\s*(?:to|-)\s*([\d.]+))?\s*hours?\s*(per week|weekly|bi-weekly|per month|monthly)?",
                  text or "", re.I)
    if not m:
        return {"hours_min": None, "hours_max": None, "hours_per": None}
    lo = float(m.group(1))
    hi = float(m.group(2)) if m.group(2) else lo
    per = (m.group(3) or "week").lower()
    per = "Bi-weekly" if "bi" in per else "Month" if "month" in per else "Week"
    return {"hours_min": lo, "hours_max": hi, "hours_per": per}


def _posted_date(soup: BeautifulSoup) -> str | None:
    m = re.search(r"[A-Z][a-z]+ \d{1,2}, \d{4}|\d{4}-\d{2}-\d{2}", _prop_text(soup, "datePosted") or "")
    if not m:
        return None
    for fmt in ("%B %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(m.group(0), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _arrangement(soup: BeautifulSoup) -> str | None:
    value = _labelled(soup, "Work location")
    if value:
        return next((name for name, pat in ARRANGEMENTS if pat.search(value)), value)
    return None


def _source(soup: BeautifulSoup) -> str | None:
    """Site the posting came from: 'Job Bank', 'indeed.com', 'Jobillico', ... (posting number dropped)."""
    value = _labelled(soup, "Source")
    return _clean(re.sub(r"#\S+", "", value)) if value else None


def parse_posting(html: str | bytes, posting_id: str) -> dict:
    soup = _soup(html)
    main = soup.find("main") or soup
    title, standard_title = _title(main)
    employer = _prop(main, "hiringOrganization")
    education = _section(main, "Education")
    experience = _section(main, "Experience")
    noc = main.find(string=re.compile(r"\bNOC\s*\d{5}\b"))

    return {
        "job_number": posting_id,
        "url": f"https://www.jobbank.gc.ca/jobsearch/jobposting/{posting_id}",
        "title": title,
        "standard_title": standard_title,
        "employer": _clean(employer.get_text(" ")) if employer else None,
        "city": _prop_text(main, "addressLocality"),
        "province": _prop_text(main, "addressRegion"),
        "posted_date": _posted_date(main),
        "work_arrangement": _arrangement(main),
        "education": "; ".join(education) or None,
        "experience": experience[0] if experience else None,
        "noc_code": re.search(r"\d{5}", noc).group(0) if noc else None,
        "source": _source(main),
        "skills": _section(main, "Computer and technology knowledge"),
        "tasks": _section(main, "Tasks"),
        **_salary(main),
        **_hours(main),
    }


CORE_FIELDS = ["title", "employer", "province", "posted_date", "salary_min", "work_arrangement"]


def parse_quality(records: list[dict]) -> dict[str, float]:
    """Share of records where each core field was found — a drop signals a layout change.

    `skills` is reported too, but it's expected to be low: only postings made
    directly on Job Bank have a skills list.
    """
    n = max(len(records), 1)
    return {f: sum(bool(r.get(f)) for r in records) / n for f in CORE_FIELDS + ["skills"]}
