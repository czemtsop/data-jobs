"""
Coordinator for managing multiple job board scrapers.
"""

import pandas as pd
from typing import List, Dict
import logging

from scraper.base_scraper import ScraperFactory

logger = logging.getLogger(__name__)


class ScraperCoordinator:
    """Coordinates multiple job board scrapers."""

    def __init__(self, config: Dict):
        self.config = config
        self.scrapers_config = config.get('scrapers', {})
        self.keywords = config.get('filters', {}).get('keywords', ['data'])

    def fetch_all_jobs(self, scraper_names: List[str] = None) -> pd.DataFrame:
        """
        Fetch jobs from all enabled scrapers or specified scrapers.

        Args:
            scraper_names: List of scraper names to use. If None, uses all enabled scrapers.

        Returns:
            Combined DataFrame of all job listings.
        """
        if scraper_names is None:
            scraper_names = [name for name, config in self.scrapers_config.items()
                             if config.get('enabled', False)]

        if not scraper_names:
            logger.warning("No scrapers enabled or specified")
            return pd.DataFrame()

        logger.info(f"Starting job collection from scrapers: {scraper_names}")

        all_jobs = []

        for scraper_name in scraper_names:
            if scraper_name not in self.scrapers_config:
                logger.error(f"Scraper '{scraper_name}' not found in configuration")
                continue

            scraper_config = self.scrapers_config[scraper_name]

            if not scraper_config.get('enabled', False):
                logger.info(f"Skipping disabled scraper: {scraper_name}")
                continue

            try:
                logger.info(f"Initializing {scraper_name} scraper")
                scraper = ScraperFactory.create_scraper(scraper_name, scraper_config)

                logger.info(f"Fetching jobs from {scraper_name}")
                jobs_df = scraper.scrape_jobs(self.keywords)

                if not jobs_df.empty:
                    all_jobs.append(jobs_df)
                    logger.info(f"Successfully fetched {len(jobs_df)} jobs from {scraper_name}")
                else:
                    logger.warning(f"No jobs returned from {scraper_name}")

            except Exception as e:
                logger.error(f"Error scraping from {scraper_name}: {str(e)}")
                continue

        if not all_jobs:
            logger.warning("No jobs were successfully scraped from any source")
            return pd.DataFrame()

        # Combine all DataFrames
        combined_df = pd.concat(all_jobs, ignore_index=True)

        # Remove duplicates based on URL (assuming URLs are unique identifiers)
        original_count = len(combined_df)
        combined_df = combined_df.drop_duplicates(subset=['url'], keep='first')
        final_count = len(combined_df)

        if original_count > final_count:
            logger.info(f"Removed {original_count - final_count} duplicate jobs")

        logger.info(f"Successfully collected {final_count} unique jobs from {len(all_jobs)} sources")

        return combined_df

    def get_available_scrapers(self) -> List[str]:
        """Get list of available scraper names."""
        return list(self.scrapers_config.keys())

    def get_enabled_scrapers(self) -> List[str]:
        """Get list of enabled scraper names."""
        return [name for name, config in self.scrapers_config.items()
                if config.get('enabled', False)]