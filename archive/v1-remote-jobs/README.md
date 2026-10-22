# v1 — Remote data jobs scraper (May 2025)

The first version of this project: scrapers for the RemoteOK and Jobicy APIs, keyword and salary analysis, and a matplotlib dashboard. It collected 60 postings over May 2025, mostly US-based remote roles.

Kept for reference. Both boards returned JSON from an API, so BeautifulSoup was only used to strip HTML out of job descriptions. It was replaced by the version at the repo root, which scrapes Job Bank's HTML pages directly, because a two-board sample of remote roles was too small and too US-heavy to say anything about the Canadian analyst market.

Some of its dependencies (nltk, matplotlib, seaborn, wordcloud) are no longer in the root `pyproject.toml`; install them separately to run this code. Paths in `main.py` assume the old layout.
