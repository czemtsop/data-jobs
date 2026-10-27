# data-jobs — Canadian Analyst Job Market

BI showcase: Job Bank (jobbank.gc.ca) analyst postings → Power BI. Live BeautifulSoup scrape for current postings + ESDC monthly open data (Jan 2024 – Sep 2026, `source.first_month` in config) for history. Work is on branch `canada-analyst-powerbi`, draft PR #1 against `master`.

## Layout
- `scraper/` — `fetch.py` (polite client, ≥5 s delay per robots.txt), `parse.py` (BeautifulSoup; finds fields by schema.org `property` attributes, screen-reader labels and section headings, not CSS classes), `store.py` (merges into `data/scraped/postings.csv` + `skills.csv`). Run: `uv run python -m scraper [--max-pages N] [--save-html DIR] [--reparse DIR]`. Checked against the live site 2026-10-22; fixtures in `tests/fixtures/` are real saved pages. Partner-site postings (most) have no skills/tasks lists, so skill coverage is ~25%. Job Bank's search maps "analyst" to occupation codes, so most results aren't analyst titles and get dropped by the title filter.
- `pipeline/` — `load.py` (header mapping for the UTF-16 tab-separated Job Bank CSVs), `scraped.py` (keeps only scraped postings newer than the latest open-data date), `transform.py`, `model.py` (star schema → `data/model/`), `findings.py` (writes the README block between `<!-- FINDINGS:START/END -->`), `download.py` (fetches missing monthly CSVs via the open.canada.ca CKAN API; `data/job-bank/` is gitignored). Run: `uv run python -m pipeline run` (downloads first; `--no-download` to skip).
- `config/config.yaml` — title filters, role families, seniority, salary assumptions, scrape settings.
- `powerbi/` — `BUILD.md`, `measures.dax`, `theme.json`. No `.pbix` yet.
- `deploy/scrape.yml` — daily GitHub Actions workflow; must be moved to `.github/workflows/` (the cloud session's token couldn't push workflow files).
- `archive/v1-remote-jobs/` — original 2025 RemoteOK/Jobicy project, kept for reference.

## Rules
- README order is fixed: business question, data, approach, 3–5 findings with numbers, dashboard image, how to run.
- Never hand-edit numbers in the Findings block; change `pipeline/findings.py` and rerun the pipeline.
- Medians, not means; don't rank groups with < 30 salaried postings.
- Salary coverage jumped from ~30% (2024) to 100% (Dec 2025 on). Cross-year pay comparisons use Job Bank direct postings only; pay rankings use the latest year only.
- Jun–Sep 2024 files have no posting ID column; `load.py` assigns file+row IDs.
- EN and FR monthly files were cross-checked once (Oct 2026): same postings, same values when joined on posting ID, but different row order. Don't re-add the comparison to the pipeline.
- Match on the employer's original title: Job Bank's auto-assigned standard title is unreliable for external postings.

## Open items
1. Move `deploy/scrape.yml` to `.github/workflows/scrape.yml`.
2. Build the `.pbix` from `powerbi/BUILD.md`, export `docs/dashboard.png`.
3. Optional: the raw CSVs are no longer tracked, but ~410 MB remains in master's history (commit `d7bde02`); shrinking that needs a history rewrite + force-push.
