# Building the Power BI report

Everything Power BI needs is in `data/model/` after `python -m pipeline run`.
This guide rebuilds `powerbi/canada-analyst-market.pbix` from scratch in about an hour.

## 1. Load the data

**Get data → Text/CSV**, load all seven files from `data/model/`:

| Table | Grain | Key |
|---|---|---|
| `fact_postings` | one row per posting | `posting_id` |
| `dim_province` | one row per province/territory | `province_code` |
| `dim_role_family` | one row per role family | `role_family` |
| `dim_seniority` | Junior / Mid / Senior / Manager | `seniority` |
| `dim_date` | one row per calendar day | `date` |
| `bridge_posting_skill` | one row per (posting, tool) — live-scraped postings only | `posting_id`, `skill` |
| `dim_skill` | one row per tool, with posting count | `skill` |

In Power Query, check types: `posted_date` and `dim_date[date]` = Date; salary columns = Decimal; `vacancies` = Whole number; `has_salary` = True/False; `noc_code` = **Text** (keeps leading zeros).

> Tip: point the folder path at a parameter (`ModelFolder`) so anyone who clones the repo changes one value and refreshes.

## 2. Model

Star schema, all relationships many-to-one, single direction, from the fact to each dimension:

```
dim_date[date]                ──1:*── fact_postings[posted_date]
dim_province[province_code]   ──1:*── fact_postings[province_code]
dim_role_family[role_family]  ──1:*── fact_postings[role_family]
dim_seniority[seniority]      ──1:*── fact_postings[seniority]
dim_skill[skill]              ──1:*── bridge_posting_skill[skill]
fact_postings[posting_id]     ──1:*── bridge_posting_skill[posting_id]   (cross-filter: Both)
```

The bridge relationship is the one place filtering runs both ways, so picking a tool in a slicer filters the postings that ask for it.

- Mark `dim_date` as the date table (column `date`).
- Sort `dim_seniority[seniority]` by `sort_order`, `dim_date[month]` by `month_start`, and `dim_role_family[role_family]` by `sort_order` (keeps "Other analyst" last).
- Set `dim_province[province_name]` data category to **State or Province**.
- Hide the key columns on the fact table and the `sort_order` columns.

## 3. Measures

Create a `_Measures` table and add the measures in [`measures.dax`](measures.dax). Format: salaries as currency, 0 decimals, display units Thousands; the `%` measures as percentage, 0 decimals.

## 4. Theme

**View → Themes → Browse for themes** → [`theme.json`](theme.json). Blue (`#2a78d6`) is the single series colour; the full categorical order is only used if a visual splits by role family.

## 5. Page layout — "Canadian Analyst Job Market" (16:9)

```
┌────────────────────────────────────────────────────────────────────────┐
│ Title + [Report Scope] subtitle                     Slicers: Month ▾   │
│                              Province ▾ Family ▾ Source ▾ Data source ▾│
├──────────────┬──────────────┬──────────────┬───────────────────────────┤
│ Postings     │ Vacancies    │ Median salary│ Salary coverage %         │
├──────────────┴──────────────┼──────────────┴───────────────────────────┤
│ Map: Postings by province   │ Bar: Postings by role family (sorted)    │
│ (filled map, sat. = Postings)│                                         │
├─────────────────────────────┼──────────────────────────────────────────┤
│ Bar: Median Salary (reliable)│ Column: Median salary by seniority      │
│ by role family + P25–P75     │ Line: Postings by week                  │
│ error bars                   │                                         │
└─────────────────────────────┴──────────────────────────────────────────┘
```

Second page — **"Right now" (live scrape)**, filtered to `data_source = "Live scrape"`:

```
┌──────────────────────────────┬─────────────────────────────────────────┐
│ Bar: Top 10 tools by          │ Bar: Postings by work arrangement       │
│ [Tool Share] (dim_skill)      │ (On site / Hybrid / Remote)             │
├──────────────────────────────┴─────────────────────────────────────────┤
│ Table: latest postings — date, title, employer, city, salary, link     │
└────────────────────────────────────────────────────────────────────────┘
```

Visual notes:

- **KPI cards** — `[Postings]`, `[Vacancies]`, `[Median Salary]`, `[Salary Coverage %]`.
- **Map** — Filled map, Location = `dim_province[province_name]`, colour saturation = `[Postings]` (single blue, light → dark). Tooltip: `[Postings]`, `[Median Salary (reliable)]`, `[Pay vs Canada %]`.
- **Postings by role family** — clustered bar, sorted descending, data labels = `[Share of Postings]`.
- **Pay by role family** — clustered bar of `[Median Salary (reliable)]`; Analytics pane → error bars with `[Salary P25]` / `[Salary P75]` as lower/upper bounds. Families under 30 salaried postings show blank by design.
- **Seniority** — column chart, axis `dim_seniority[seniority]`, value `[Median Salary (reliable)]`.
- **Trend** — line chart, axis `dim_date[week_start]`, value `[Postings]`. One axis only.
- **Data source slicer** — `fact_postings[data_source]`: "Open data" (monthly files) or "Live scrape" (postings newer than the latest file).
- **Tools** — bar of `[Tool Share]` by `dim_skill[skill]`, Top N = 10 filter on `[Postings Listing Tools]`. Show the n in the subtitle; hide the visual (or show a note) when fewer than 30 postings list tools.
- **Work arrangement** — open-data rows are "Not captured"; filter them out of this visual.
- **Source slicer** — `fact_postings[posting_source]` (Job Bank direct vs External job board), so viewers can check findings hold for both.
- Keep gridlines dotted, no data labels on every point, legend off for single-series visuals.

## 6. Export the README image

Set slicers to "All", then **File → Export → PDF** (or a 1600 px-wide screenshot) and save the page as `docs/dashboard.png`. Commit it together with the `.pbix`.
