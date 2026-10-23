# Canadian Analyst Job Market

This is an analysis of analyst job postings across Canada based on data from the federal job bank, [jobbank.gc.ca](https://www.jobbank.gc.ca). A BeautifulSoup scraper collects current postings from the site every day, and the site's [open data platform](https://open.canada.ca/data/en/dataset/ea639e28-c0fc-48bf-b5dd-b8899bd43072) supplies the history behind them.

## Business questions

1. **Where in Canada are employers hiring analysts right now?**
2. **Which kinds of analyst roles and tools are in demand, and what do they advertise as pay?**
3. **How is this changing over time?**

The audience is an analyst jobseeker (or a career advisor, or a training provider) deciding where to apply, which specialisation to build toward, and what salary to expect — using what employers actually posted rather than survey estimates.

## Data

Two sources from the same job board, combined so the dashboard is current and has history at the same time:

|               | Live scrape                                                                                 | Monthly open data                                                                                              |
|---------------|---------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------|
| **What**      | Job Bank search and posting pages, scraped with `requests` + BeautifulSoup                  | Every posting first advertised in a month, published as CSV by Employment and Social Development Canada (ESDC) |
| **Freshness** | Daily (scheduled run)                                                                       | Each month is published a few weeks after it ends                                                              |
| **Adds**      | on-site / hybrid / remote, tools listed under *Computer and technology knowledge*, employer | 33 months of history (Jan 2024 – Sep 2026), consistent fields, original vs standard title                      |
| **Used for**  | postings first posted *after* the latest monthly file                                       | everything up to the latest monthly file                                                                       |

The two use different IDs and can't be matched row by row, so a scraped posting is only kept if it was first posted after the latest open-data date. When the next monthly file is published, those weeks switch over to the official data automatically.

**Scraping etiquette.** jobbank.gc.ca's robots.txt allows crawling with a 5-second delay; the scraper waits at least that long between requests, identifies itself with a project user-agent, and stops paging once it reaches postings it has already stored.

### Monthly open data

|                 |                                                                                                                                                                                                                                 |
|-----------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Source**      | [Job Postings Advertised on Canada's National Job Bank](https://open.canada.ca/data/en/dataset/ea639e28-c0fc-48bf-b5dd-b8899bd43072), Employment and Social Development Canada                                                  |
| **Licence**     | [Open Government Licence – Canada](https://open.canada.ca/en/open-government-licence-canada)                                                                                                                                    |
| **Format**      | One CSV per month of first posting (English and French files); this project uses the English files for January 2024 – September 2026 — 2,555,516 postings in total, downloaded to `data/job-bank/` by the pipeline |
| **Fields used** | original and standard job title, NOC 2021 code, province/territory, city, economic region, first posting date, salary min/max and period, hours min/max and period, vacancies, employment type/term, external-posting indicator |
| **Scope**       | Postings whose title contains *analyst* / *analytics* (or French *analyste*), located in a Canadian province or territory — 33,447 postings                                                                                     |

**Two kinds of posting, two kinds of title.** About 88% of the analyst postings come from external job boards that feed Job Bank; the rest were posted on Job Bank directly. External postings carry the employer's own wording ("Original Job Title") plus a standard NOC title that Job Bank assigns automatically — and that assigned title is often wrong: of 2,384 external postings coded *information technology (IT) analyst* that include the employer's title, only about 1% had "analyst" in the employer's title (most were "… Specialist" roles). The pipeline therefore matches on the employer's title whenever one exists.

**English and French files.** ESDC publishes every month in both official languages. The pipeline uses the English files; a one-time cross-check against the French files, with postings paired by ID, found the same postings with matching values in every coded and numeric field. The two files list postings in a different order, so they can't be compared row by row.

**Limitations.**
- Job Bank only covers employers who advertise there or on a contributing board, so its mix may differ from LinkedIn or Indeed (couldn't scrape either of them due to strict prohibitions in their user agreements.)
- Salaries are *advertised* ranges, not offers. How often a posting lists one changed over time: partner-site postings rarely did before mid-2025, and every posting has since December 2025. Pay trends therefore use postings made directly on Job Bank, and pay rankings use 2026 only.
- Fewer partner-site postings carry the employer's own title in 2026 (61%) than in 2024 (75%), so more of the 2026 title matching relies on Job Bank's standard title.
- Title matching is transparent but imperfect — see the patterns in [`config/config.yaml`](config/config.yaml).
- Job Bank's telework field is never "Yes" in the monthly files, so work arrangement and tools come only from the live scrape and cover a shorter window.
- The scraper reads fields by their visible labels on the page; if Job Bank redesigns its pages, the run logs field coverage and refuses to save when titles go missing.
- The changes in salaries and the number of job postings might say more about job bank's data collection methods than about real trends in the job market.

## Approa

```
jobbank.gc.ca ─► scraper/ (requests + BeautifulSoup) ─► data/scraped/ ─┐
                 search pages → posting IDs                             │
                 posting pages → fields, tools, arrangement             ├─► pipeline/ ─► data/model/ ─► Power BI
Job Bank monthly CSVs (data/job-bank/) ─────────────────────────────────┘   filter, derive,  star schema   (powerbi/)
                                                                              findings
```

0. **Scrape** — `python -m scraper` pages through Job Bank search results for *analyst* / *analyste* (newest first), collects posting IDs it hasn't seen, then fetches each posting page and parses it with BeautifulSoup: title, employer, city/province, posted date, salary, hours, work arrangement, education, experience, NOC code, tasks, and the tools listed under *Computer and technology knowledge*. New postings are merged into `data/scraped/postings.csv` and `skills.csv`.
1. **Load** — each month's file is read with encoding and delimiter detection, and its headers are mapped to a canonical schema (`python -m pipeline inspect` shows the mapping).
2. **Filter** — keep Canadian postings with an analyst title; drop clinical "behaviour analyst" roles and duplicate posting IDs. Each monthly file holds postings *first posted* that month, so months don't overlap.
3. **Derive**
   - *Title* — the employer's original title where present, otherwise the posted title.
   - *Role family* (Data & BI, Financial, Business & Systems, IT Support & Security, Marketing & Sales, Policy & Research, Operations & Supply Chain, Lab & Quality, Other) from title keywords in English and French, first match wins. About 9% of postings stay "Other" — mostly generic titles such as "Analyst" or "Senior Analyst".
   - *Seniority* (Junior / Mid / Senior / Manager) from title keywords.
   - *Annual salary* — hourly × weekly hours (from the posting's hours range; 37.5 if missing) × 52; daily × 260; weekly × 52; bi-weekly × 26; monthly × 12. Midpoint of min/max; values outside $25K–$400K are treated as unusable.
4. **Model** — one fact table (`fact_postings`), four dimensions (province, role family, seniority, date) and a posting–tool bridge (`bridge_posting_skill`, `dim_skill`) for Power BI. See [`powerbi/BUILD.md`](powerbi/BUILD.md) for relationships, DAX measures and layout.
5. **Report** — medians rather than means (salaries are skewed), and no group is ranked on fewer than 30 salaried postings. The month-over-month trend uses complete open-data months only. A tools finding appears once at least 30 scraped postings list tools. The findings below are written by `pipeline/findings.py`, so they refresh whenever the pipeline is rerun.

## Findings

<!-- FINDINGS:START -->
1. **Analyst demand shrank.** Jan–Sep analyst postings fell 72%, from 14,490 in 2024 to 3,985 in 2026, while all Job Bank postings fell 53%; analysts went from 1.5% to 0.9% of all postings.
2. **Advertised pay was flat.** Postings made directly on Job Bank, which always list a salary, had a median of $76K in Jan–Sep 2024 and $78K in 2026 (n=1,765 and 700). The median across all postings rose 16%, but mostly because the share listing a salary went from 29% to 99%.
3. **The mix moved toward data roles.** Data & BI went from 13% of analyst postings in 2024 to 17% in 2026; Financial analysts are still the largest group at 31%.
4. **Financial analysts are the largest group** at 31% of postings; Data & BI roles are 17%.
5. **The kind of analyst matters for pay.** Data & BI postings in 2026 advertise a median $92K (n=672), 32% more than Marketing & Sales at $70K (n=81).
6. **Demand is concentrated.** Ontario and Quebec account for 71% of the 3,985 analyst postings (Ontario alone 52       │7 tests/generated.
7. **Pay differs between the two biggest markets.** The median in 2026 is $91K in Ontario versus $78K in Quebec, 14% lower (national median $88K).

<sub>Job Bank postings with an analyst title, first posted 2024-01-01 to 2026-10-22 (34 months). Includes 4 postings scraped from jobbank.gc.ca after the latest monthly file. Salaries are advertised ranges converted to annual CAD (midpoint). Year-over-year comparisons use the same months (Jan–Sep) in each year. Pay rankings use 2026 only, when 99% of postings list a salary (42% across the whole period). Medians are only compared for groups with at least 30 salaried postings.</sub>
<!-- FINDINGS:END -->

## Dashboard

![Canadian Analyst Job Market dashboard](docs/dashboard.png)

Built in Power BI Desktop — [`powerbi/canada-analyst-market.pbix`](powerbi/). Two pages: the market overview (filters by month, province, role family, seniority, posting source and data source) and *Right now* (tools and work arrangement from the live scrape).

## How to run

**Requirements:** Python 3.12+, [uv](https://docs.astral.sh/uv/) (or pip), Power BI Desktop (Windows) for the report.

```bash
git clone https://github.com/czemtsop/data-jobs.git
cd data-jobs
uv sync
```

1. **Scrape current postings** (about 5 s per page, so a first run takes 30+ minutes; later runs only fetch what's new):
   ```bash
   uv run python -m scraper                  # all configured queries
   uv run python -m scraper --max-pages 1 --save-html data/scraped/html   # quick test, keeps the raw pages
   ```
   To run it every day, move [`deploy/scrape.yml`](deploy/scrape.yml) to `.github/workflows/` and push: GitHub Actions will scrape, rebuild the tables and commit the results each morning.
2. **Monthly data.** The open-data CSVs (~45 MB each) aren't stored in git. `pipeline run` downloads any missing months from the [Job Bank dataset page](https://open.canada.ca/data/en/dataset/ea639e28-c0fc-48bf-b5dd-b8899bd43072) into `data/job-bank/`, starting from `source.first_month` in `config/config.yaml`. To fetch them on their own:
   ```bash
   uv run python -m pipeline download
   ```
3. **Check the headers mapped** (Job Bank has changed column names between releases):
   ```bash
   uv run python -m pipeline inspect
   ```
4. **Build the model and findings:**
   ```bash
   uv run python -m pipeline run
   ```
   Writes `data/model/*.csv`, `data/model/findings.json`, and refreshes the Findings section above.
5. **Open the report.** Open `powerbi/canada-analyst-market.pbix` and click **Refresh**, or build it from scratch with [`powerbi/BUILD.md`](powerbi/BUILD.md).
6. **Tests:** `uv run pytest`

```
config/config.yaml   filters, role-family and seniority rules, salary assumptions, scrape settings
scraper/             fetch (polite client) → parse (BeautifulSoup) → store
pipeline/            load → transform → model → findings
deploy/scrape.yml    daily GitHub Actions run (move into .github/workflows/ to enable)
data/scraped/        scraped postings and their tools (grows daily)
powerbi/             BUILD.md, measures.dax, theme.json, .pbix
data/job-bank/       Job Bank monthly CSVs, Jan 2024 – Sep 2026 (~1.9 GB, downloaded, not in git)
data/model/          star-schema CSVs Power BI reads (committed)
docs/                dashboard image
archive/v1-remote-jobs/  the original 2025 remote-jobs scraper (RemoteOK / Jobicy)
```

---

Licensed under GPL-3.0. Job Bank data © Government of Canada, used under the Open Government Licence – Canada.
