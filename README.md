# Canadian Analyst Job Market

A Power BI analysis of analyst job postings across Canada, built on the federal Job Bank's open data.

## Business question

**Where in Canada are employers hiring analysts, which kinds of analyst roles are in demand, and what do they advertise as pay?**

The audience is an analyst job seeker (or a career advisor, or a training provider) deciding where to apply, which specialisation to build toward, and what salary to expect — using what employers actually posted rather than survey estimates.

## Data

| | |
|---|---|
| **Source** | [Job Postings Advertised on Canada's National Job Bank](https://open.canada.ca/data/en/dataset/ea639e28-c0fc-48bf-b5dd-b8899bd43072), Employment and Social Development Canada |
| **Licence** | [Open Government Licence – Canada](https://open.canada.ca/en/open-government-licence-canada) |
| **Format** | One CSV per month of first posting (English and French files); this project uses the English files for January–September 2026 — 461,934 postings in total, stored in [`data/job-bank/`](data/job-bank/) |
| **Fields used** | original and standard job title, NOC 2021 code, province/territory, city, economic region, first posting date, salary min/max and period, hours min/max and period, vacancies, employment type/term, external-posting indicator |
| **Scope** | Postings whose title contains *analyst* / *analytics* (or French *analyste*), located in a Canadian province or territory — 3,985 postings |

**Two kinds of posting, two kinds of title.** About 82% of the analyst postings come from external job boards that feed Job Bank; the rest were posted on Job Bank directly. External postings carry the employer's own wording ("Original Job Title") plus a standard NOC title that Job Bank assigns automatically — and that assigned title is often wrong: of 2,384 external postings coded *information technology (IT) analyst* that include the employer's title, only about 1% had "analyst" in the employer's title (most were "… Specialist" roles). The pipeline therefore matches on the employer's title whenever one exists.

**Limitations.** Job Bank only covers employers who advertise there or on a contributing board, so its mix may differ from LinkedIn or Indeed. Salaries are *advertised* ranges, not offers. Title matching is transparent but imperfect — see the patterns in [`config/config.yaml`](config/config.yaml). Job Bank's telework field is never "Yes" in these files, so remote work is not analysed.

## Approach

```
Job Bank monthly CSVs ─► pipeline/load.py ─► pipeline/transform.py ─► pipeline/model.py ─► Power BI
 (data/job-bank/)          header mapping,      analyst filter, dedupe,   star schema CSVs      (powerbi/)
                          encoding sniffing    salary → annual CAD,      (data/model/)
                                               role family, seniority
```

1. **Load** — each month's file is read with encoding and delimiter detection, and its headers are mapped to a canonical schema (`python -m pipeline inspect` shows the mapping).
2. **Filter** — keep Canadian postings with an analyst title; drop clinical "behaviour analyst" roles and duplicate posting IDs. Each monthly file holds postings *first posted* that month, so months don't overlap.
3. **Derive**
   - *Title* — the employer's original title where present, otherwise the posted title.
   - *Role family* (Data & BI, Financial, Business & Systems, IT Support & Security, Marketing & Sales, Policy & Research, Operations & Supply Chain, Lab & Quality, Other) from title keywords in English and French, first match wins. About 9% of postings stay "Other" — mostly generic titles such as "Analyst" or "Senior Analyst".
   - *Seniority* (Junior / Mid / Senior / Manager) from title keywords.
   - *Annual salary* — hourly × weekly hours (from the posting's hours range; 37.5 if missing) × 52; daily × 260; weekly × 52; bi-weekly × 26; monthly × 12. Midpoint of min/max; values outside $25K–$400K are treated as unusable.
4. **Model** — one fact table (`fact_postings`) and four dimensions (province, role family, seniority, date) for Power BI. See [`powerbi/BUILD.md`](powerbi/BUILD.md) for relationships, DAX measures and layout.
5. **Report** — medians rather than means (salaries are skewed), and no group is ranked on fewer than 30 salaried postings. The findings below are written by `pipeline/findings.py`, so they refresh whenever the pipeline is rerun.

## Findings

<!-- FINDINGS:START -->
1. **Demand is concentrated.** Ontario and Quebec account for 71% of the 3,985 analyst postings (Ontario alone 52%).
2. **Analyst hiring cooled.** Monthly analyst postings fell 33%, from an average of 559 in Jan–Mar to 377 in Jul–Sep 2026, while all Job Bank postings rose 9% over the same period.
3. **Financial analysts are the largest group** at 31% of postings; Data & BI roles are 17%.
4. **The kind of analyst matters for pay.** Data & BI postings advertise a median $92K (n=672), 32% more than Marketing & Sales at $70K (n=81).
5. **Pay differs between the two biggest markets.** The median is $91K in Ontario versus $78K in Quebec, 14% lower (national median $88K).

<sub>Job Bank postings with an analyst title, first posted 2026-01-01 to 2026-09-30 (9 months). Salaries are advertised ranges converted to annual CAD (midpoint); 99% of postings include one. Medians are only compared for groups with at least 30 salaried postings.</sub>
<!-- FINDINGS:END -->

## Dashboard

![Canadian Analyst Job Market dashboard](docs/dashboard.png)

Built in Power BI Desktop — [`powerbi/canada-analyst-market.pbix`](powerbi/). Filters by month, province, role family, seniority and posting source.

## How to run

**Requirements:** Python 3.12+, [uv](https://docs.astral.sh/uv/) (or pip), Power BI Desktop (Windows) for the report.

```bash
git clone https://github.com/czemtsop/data-jobs.git
cd data-jobs
uv sync
```

1. **Data.** January–September 2026 is already in `data/job-bank/`. To add months, download more English files (`job-bank-open-data-all-job-postings-en-<month><year>.csv`) from the [Job Bank dataset page](https://open.canada.ca/data/en/dataset/ea639e28-c0fc-48bf-b5dd-b8899bd43072) into the same folder.
2. **Check the headers mapped** (Job Bank has changed column names between releases):
   ```bash
   uv run python -m pipeline inspect
   ```
3. **Build the model and findings:**
   ```bash
   uv run python -m pipeline run
   ```
   Writes `data/model/*.csv`, `data/model/findings.json`, and refreshes the Findings section above.
4. **Open the report.** Open `powerbi/canada-analyst-market.pbix` and click **Refresh**, or build it from scratch with [`powerbi/BUILD.md`](powerbi/BUILD.md).
5. **Tests:** `uv run pytest`

```
config/config.yaml   filters, role-family and seniority rules, salary assumptions
pipeline/            load → transform → model → findings
powerbi/             BUILD.md, measures.dax, theme.json, .pbix
data/job-bank/       Job Bank monthly CSVs, Jan–Sep 2026 (~410 MB)
data/model/          star-schema CSVs Power BI reads (committed)
docs/                dashboard image
archive/v1-remote-jobs/  the original 2025 remote-jobs scraper (RemoteOK / Jobicy)
```

---

Licensed under GPL-3.0. Job Bank data © Government of Canada, used under the Open Government Licence – Canada.
