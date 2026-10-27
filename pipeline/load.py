"""Load Job Bank open-data CSVs and map their headers onto a canonical schema.

The monthly files are published by ESDC on open.canada.ca. Header wording has
shifted between releases, so columns are matched against a list of candidate
names (case, spacing and punctuation ignored) rather than hard-coded.
Run `python -m pipeline inspect` to see how a file's headers were mapped.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from pathlib import Path

import pandas as pd

from .download import in_range, month_of

# canonical name -> candidate header spellings (normalized: lowercase alphanumerics only)
COLUMN_CANDIDATES: dict[str, list[str]] = {
    "posting_id": ["wicjoblocationsnapshotid", "jobpostingid", "postingid", "jobid", "id", "jobbanknumber", "jobbankid"],
    # Job Bank has two titles: "Original Job Title" (what the employer wrote; only on
    # postings from external job boards) and "Job Title" (a standardized NOC title,
    # assigned automatically for external postings). transform.py prefers the original.
    "original_title": ["originaljobtitle"],
    "title": ["jobtitle", "title", "jobtitleen", "positiontitle"],
    "noc_code": ["noc21code", "noc2021code", "noccode", "noc21", "noc"],
    "noc_name": ["noc21codename", "noc21name", "nocname", "noctitle", "noc21title", "noccodename"],
    "province": ["provinceterritory", "province", "provinceorterritory", "prov", "workprovince"],
    "city": ["city", "worklocation", "location", "worklocationcity", "municipality"],
    "posted_date": ["firstpostingdate", "postingdate", "dateposted", "posteddate", "datepublished", "publicationdate", "startdate"],
    "salary_min": ["salaryminimum", "salarymin", "minimumsalary", "wagemin", "salaryfrom", "wagelow"],
    "salary_max": ["salarymaximum", "salarymax", "maximumsalary", "wagemax", "salaryto", "wagehigh"],
    "salary_per": ["salaryper", "salaryperiod", "wageper", "salarytype", "salaryunit", "payperiod"],
    "hours_min": ["hoursminimum", "hoursmin", "minimumhours"],
    "hours_max": ["hoursmaximum", "hoursmax", "maximumhours"],
    "hours_per": ["hoursper", "hoursperiod"],
    "vacancies": ["vacancycount", "vacancies", "numberofvacancies", "numberofpositions", "positions"],
    "employment_type": ["employmenttype", "fulltimeparttime", "jobtype"],
    "employment_term": ["employmentterm", "term", "jobterm"],
    "external": ["externalindicator", "external"],
    "naics_code": ["naicscode", "naics", "industrycode"],
    "economic_region": ["economicregion"],
    "education": ["educationlos", "education", "educationlevel", "levelofstudy"],
    "experience": ["experiencelevel", "experience", "experiencerequired"],
}

REQUIRED = ["title", "province", "posted_date"]


def _norm(header: str) -> str:
    plain = unicodedata.normalize("NFKD", str(header)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", plain.lower())


def _detect_encoding(raw: bytes) -> str:
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "cp1252"


def read_raw(path: Path) -> pd.DataFrame:
    """Read one CSV, sniffing encoding and delimiter (gov files vary)."""
    head = path.open("rb").read(200_000)
    encoding = _detect_encoding(head)
    sample = head.decode(encoding, errors="ignore")
    try:
        delimiter = csv.Sniffer().sniff(sample.splitlines()[0], delimiters=",\t;|").delimiter
    except (csv.Error, IndexError):
        delimiter = ","
    return pd.read_csv(path, encoding=encoding, sep=delimiter, dtype=str,
                       keep_default_na=False, na_values=["NA", "N/A", ""], low_memory=False)


def map_columns(columns: list[str]) -> dict[str, str]:
    """Return {canonical: original_header} for every column we can identify."""
    by_norm = {_norm(c): c for c in columns}
    mapping: dict[str, str] = {}
    for canonical, candidates in COLUMN_CANDIDATES.items():
        for cand in candidates:
            if cand in by_norm and by_norm[cand] not in mapping.values():
                mapping[canonical] = by_norm[cand]
                break
    return mapping


def load_month(path: Path) -> pd.DataFrame:
    df = read_raw(path)
    mapping = map_columns(list(df.columns))
    missing = [c for c in REQUIRED if c not in mapping]
    if missing:
        raise ValueError(
            f"{path.name}: could not find required column(s) {missing}.\n"
            f"Headers in file: {list(df.columns)}\n"
            f"Add the right spelling to COLUMN_CANDIDATES in pipeline/load.py."
        )
    out = df[list(mapping.values())].rename(columns={v: k for k, v in mapping.items()})
    for col in COLUMN_CANDIDATES:
        if col not in out.columns:
            out[col] = pd.NA
    if "posting_id" not in mapping:
        # Jun-Sep 2024 files have no ID column. Each monthly file holds distinct postings,
        # so file + row number is a safe ID (blank IDs would all collapse in de-duplication).
        out["posting_id"] = [f"{path.stem}#{i}" for i in range(len(out))]
    out["source_file"] = path.name
    return out


def load_all(raw_dir: Path, pattern: str, first_month: str | None = None, last_month: str | None = None) -> pd.DataFrame:
    """All monthly files in raw_dir; with first_month set, only those in [first_month, last_month]."""
    files = sorted(raw_dir.glob(pattern))
    if first_month:
        files = [f for f in files if in_range(month_of(f.name), first_month, last_month)]
    if not files:
        raise FileNotFoundError(
            f"No CSVs matching '{pattern}' in {raw_dir}/. Run `python -m pipeline download` to fetch "
            "the monthly English files from open.canada.ca"
        )
    frames = [load_month(f) for f in files]
    return pd.concat(frames, ignore_index=True)


def inspect(raw_dir: Path, pattern: str) -> str:
    lines = []
    for f in sorted(raw_dir.glob(pattern)):
        df = read_raw(f)
        mapping = map_columns(list(df.columns))
        lines.append(f"\n{f.name}: {len(df):,} rows, {len(df.columns)} columns")
        for canonical in COLUMN_CANDIDATES:
            lines.append(f"  {canonical:17} <- {mapping.get(canonical, '(not found)')}")
        unmapped = [c for c in df.columns if c not in mapping.values()]
        lines.append(f"  unmapped headers: {unmapped}")
    return "\n".join(lines) if lines else f"No files in {raw_dir}/"
