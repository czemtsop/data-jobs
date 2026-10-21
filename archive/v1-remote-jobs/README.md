# v1 — Remote data jobs scraper (May 2025)

The first version of this project: scrapers for the RemoteOK and Jobicy APIs, keyword and salary analysis, and a matplotlib dashboard. It collected 60 postings over May 2025, mostly US-based remote roles.

Kept for reference. It was replaced by the Job Bank / Power BI version at the repo root because a two-board scrape of remote roles was too small and too US-heavy to say anything about the Canadian analyst market.

Its dependencies (requests, beautifulsoup4, nltk, matplotlib, seaborn, wordcloud) are no longer in the root `pyproject.toml`; install them separately to run this code. Paths in `main.py` assume the old layout.
