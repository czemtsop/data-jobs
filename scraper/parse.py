"""Parse Job Bank pages with BeautifulSoup.

Job Bank's CSS class names are not a published interface, so fields are found by
their *visible labels* ("Education", "Computer and technology knowledge", ...),
which is what a reader sees and changes least often. Every field is optional:
a missing label gives None rather than an exception, and `parse_quality`
reports how many core fields were found so a silent layout change shows up.
"""

from __future__ import annotations

import re
from datetime import datetime

from bs4 import BeautifulSoup, Tag

POSTING_LINK = re.compile(r"/jobsearch/jobposting/(\d+)")

# headings that start a new section on a posting page (used to stop list collection)
SECTION_HEADINGS = {
    "overview", "languages", "education", "experience", "work setting", "responsibilities", "tasks",
    "supervision", "experience and specialization", "computer and technology knowledge",
    "additional information", "security and safety", "transportation/travel information",
    "work conditions and physical capabilities", "personal suitability", "screening questions",
    "benefits", "health benefits", "financial benefits", "other benefits", "who can apply to this job?",
    "how to apply", "employer profile", "advertised until", "credentials", "certificates, licences, memberships, and courses",
    "area of specialization", "software and technology environment", "work site environment",
    "own tools/equipment", "long term benefits", "employment groups", "support for employees",
}

ARRANGEMENTS = [
    ("Remote", re.compile(r"\bremote\b|work must be completed remotely|télétravail", re.I)),
    ("Hybrid", re.compile(r"\bhybrid\b|both in person and remotely|hybride", re.I)),
    ("On site", re.compile(r"\bon site\b|work must be completed at the physical location|sur place", re.I)),
]


def _soup(html: str | bytes) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def _clean(text: str | None) -> str | None:
    if text is None:
        return None
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


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

def _lines(soup: BeautifulSoup) -> list[str]:
    main = soup.find("main") or soup.body or soup
    for t in main.find_all(["script", "style", "noscript"]):
        t.decompose()
    return [s for s in (_clean(x) for x in main.stripped_strings) if s]


def _label_index(lines: list[str], label: str, start: int = 0) -> int | None:
    label = label.lower()
    for i in range(start, len(lines)):
        if lines[i].lower().rstrip(":") == label:
            return i
    return None


def _value_after(lines: list[str], label: str) -> str | None:
    i = _label_index(lines, label)
    return lines[i + 1] if i is not None and i + 1 < len(lines) else None


def _items_after(lines: list[str], label: str, limit: int = 60) -> list[str]:
    """Lines following a section heading until the next known heading."""
    i = _label_index(lines, label)
    if i is None:
        return []
    out = []
    for line in lines[i + 1:i + 1 + limit]:
        if line.lower().rstrip(":") in SECTION_HEADINGS:
            break
        out.extend(p.strip() for p in line.split(";") if p.strip())
    return out


def _list_after_heading(soup: BeautifulSoup, label: str) -> list[str]:
    """Prefer real <li> items under a heading when the markup has them."""
    pattern = re.compile(rf"^\s*{re.escape(label)}\s*:?\s*$", re.I)
    for node in soup.find_all(string=pattern):
        heading = node.parent
        sib = heading.find_next(["ul", "ol"])
        if isinstance(sib, Tag):
            items = [_clean(li.get_text(" ")) for li in sib.find_all("li")]
            items = [x for x in items if x]
            if items:
                return [p.strip() for x in items for p in x.split(";") if p.strip()]
    return []


def _salary(lines: list[str]) -> dict:
    out = {"salary_min": None, "salary_max": None, "salary_per": None, "salary_text": None}
    for line in lines:
        m = re.search(r"\$\s?([\d,]+(?:\.\d+)?)(?:\s*(?:to|-|–)\s*\$\s?([\d,]+(?:\.\d+)?))?\s*(?:\$\s*)?"
                      r"(hourly|hour|annually|year|yearly|monthly|month|weekly|week|bi-weekly|daily|day)?",
                      line, re.I)
        if m and re.search(r"hour|annual|year|month|week|day", line, re.I):
            lo = float(m.group(1).replace(",", ""))
            hi = float(m.group(2).replace(",", "")) if m.group(2) else lo
            per_text = line.lower()
            per = next((p for k, p in [("bi-weekly", "Bi-weekly"), ("hour", "Hour"), ("annual", "Year"),
                                        ("year", "Year"), ("month", "Month"), ("week", "Week"), ("day", "Day")]
                        if k in per_text), None)
            out.update(salary_min=lo, salary_max=hi, salary_per=per, salary_text=line)
            break
    return out


def _hours(lines: list[str]) -> dict:
    for line in lines:
        m = re.search(r"([\d.]+)(?:\s*(?:to|-)\s*([\d.]+))?\s*hours?\s*(per week|weekly|bi-weekly|per month|monthly)?",
                      line, re.I)
        if m and "hour" in line.lower() and not line.lower().startswith("$"):
            lo = float(m.group(1)); hi = float(m.group(2)) if m.group(2) else lo
            per = (m.group(3) or "week").lower()
            per = "Bi-weekly" if "bi" in per else "Month" if "month" in per else "Week"
            return {"hours_min": lo, "hours_max": hi, "hours_per": per}
    return {"hours_min": None, "hours_max": None, "hours_per": None}


def _posted_date(lines: list[str]) -> str | None:
    for i, line in enumerate(lines):
        if line.lower().startswith("posted on"):
            text = line[len("posted on"):].strip(" :") or (lines[i + 1] if i + 1 < len(lines) else "")
            m = re.search(r"[A-Z][a-z]+ \d{1,2}, \d{4}|\d{4}-\d{2}-\d{2}", text)
            if not m:
                continue
            for fmt in ("%B %d, %Y", "%Y-%m-%d"):
                try:
                    return datetime.strptime(m.group(0), fmt).date().isoformat()
                except ValueError:
                    continue
    return None


def _location(lines: list[str]) -> tuple[str | None, str | None]:
    """City and province code from the first 'City, XX' or '..., City, XX A1A 1A1' line."""
    pat = re.compile(r"(?:^|,\s*)([A-Za-zÀ-ÿ'.\- ]+?),?\s+(AB|BC|MB|NB|NL|NS|NT|NU|ON|PE|QC|SK|YT)\b(?:\s+[A-Z]\d[A-Z]\s?\d[A-Z]\d)?\s*$")
    for line in lines[:120]:
        m = pat.search(line)
        if m:
            return _clean(m.group(1)), m.group(2)
    return None, None


def parse_posting(html: str | bytes, posting_id: str) -> dict:
    soup = _soup(html)
    h1 = soup.find("h1")
    title = _clean(h1.get_text(" ")) if h1 else None
    lines = _lines(soup)

    arrangement = None
    for name, pat in ARRANGEMENTS:
        if any(pat.search(l) for l in lines[:150]):
            arrangement = name
            break

    city, province = _location(lines)
    skills = (_list_after_heading(soup, "Computer and technology knowledge")
              or _items_after(lines, "Computer and technology knowledge"))
    tasks = _list_after_heading(soup, "Tasks") or _items_after(lines, "Tasks")
    source = next((l for l in lines if re.match(r"^Source\b", l, re.I)), None)
    employer = _value_after(lines, "Employer")
    if employer is None:
        hiring = soup.find(attrs={"property": "hiringOrganization"})
        employer = _clean(hiring.get_text(" ")) if hiring else None

    record = {
        "job_number": posting_id,
        "url": f"https://www.jobbank.gc.ca/jobsearch/jobposting/{posting_id}",
        "title": title,
        "employer": employer,
        "city": city,
        "province": province,
        "posted_date": _posted_date(lines),
        "work_arrangement": arrangement,
        "education": _value_after(lines, "Education"),
        "experience": _value_after(lines, "Experience"),
        "noc_code": next((m.group(1) for l in lines if (m := re.search(r"\bNOC\s*(\d{5})\b", l))), None),
        "source": source,
        "skills": skills,
        "tasks": tasks,
        **_salary(lines),
        **_hours(lines),
    }
    return record


CORE_FIELDS = ["title", "province", "posted_date", "salary_min", "work_arrangement"]


def parse_quality(records: list[dict]) -> dict[str, float]:
    """Share of records where each core field was found — a drop signals a layout change."""
    n = max(len(records), 1)
    return {f: sum(bool(r.get(f)) for r in records) / n for f in CORE_FIELDS + ["skills"]}
