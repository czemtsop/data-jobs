# data-jobs — Canadian Analyst Job Market

BI showcase: Job Bank (jobbank.gc.ca) analyst postings → Power BI. Live BeautifulSoup scrape for current postings + ESDC monthly open data (Jan–Sep 2026) for history. Work is on branch `canada-analyst-powerbi`, draft PR #1 against `master`.

## Layout
- `scraper/` — `fetch.py` (polite client, ≥5 s delay per robots.txt), `parse.py` (BeautifulSoup, finds fields by visible label text, not CSS classes), `store.py` (merges into `data/scraped/postings.csv` + `skills.csv`). Run: `uv run python -m scraper [--max-pages N] [--save-html DIR] [--reparse DIR]`.
- `pipeline/` — `load.py` (header mapping for the UTF-16 tab-separated Job Bank CSVs), `scraped.py` (keeps only scraped postings newer than the latest open-data date), `transform.py`, `model.py` (star schema → `data/model/`), `findings.py` (writes the README block between `<!-- FINDINGS:START/END -->`). Run: `uv run python -m pipeline run`.
- `config/config.yaml` — title filters, role families, seniority, salary assumptions, scrape settings.
- `powerbi/` — `BUILD.md`, `measures.dax`, `theme.json`. No `.pbix` yet.
- `deploy/scrape.yml` — daily GitHub Actions workflow; must be moved to `.github/workflows/` (the cloud session's token couldn't push workflow files).
- `archive/v1-remote-jobs/` — original 2025 RemoteOK/Jobicy project, kept for reference.

## Rules
- README order is fixed: business question, data, approach, 3–5 findings with numbers, dashboard image, how to run.
- Never hand-edit numbers in the Findings block; change `pipeline/findings.py` and rerun the pipeline.
- Medians, not means; don't rank groups with < 30 salaried postings.
- Match on the employer's original title: Job Bank's auto-assigned standard title is unreliable for external postings.

## Open items
1. **The scraper has never run against the live site.** The parser was written without access to the real HTML, and `tests/fixtures/*_hand_built.html` are invented markup. First run `uv run python -m scraper --max-pages 1 --save-html data/scraped/html`, check the "field coverage" log line, fix `scraper/parse.py` against the saved pages, then replace the hand-built fixtures with real saved pages and update `tests/test_scraper.py`.
2. Move `deploy/scrape.yml` to `.github/workflows/scrape.yml`.
3. `uv lock` (lockfile was removed when dependencies changed).
4. Build the `.pbix` from `powerbi/BUILD.md`, export `docs/dashboard.png`.
5. Optional: the nine raw CSVs on master add ~410 MB; consider Git LFS.
