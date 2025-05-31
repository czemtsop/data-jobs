"""
RemoteOK job board scraper implementation.
"""

import pandas as pd
from bs4 import BeautifulSoup
from typing import List, Dict
import logging

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


def _transform_data(df_selected: pd.DataFrame, original_df: pd.DataFrame) -> pd.DataFrame:
    """Apply RemoteOK-specific data transformations."""
    # Convert 'epoch' to datetime objects
    if 'epoch' in original_df.columns:
        df_selected['epoch'] = pd.to_datetime(original_df['epoch'], unit='D', errors='coerce')

    # Convert 'tags' list into a comma-separated string
    if 'tags' in df_selected.columns:
        df_selected['tags'] = df_selected['tags'].apply(
            lambda tags_list: ', '.join(tags_list) if isinstance(tags_list, list) and tags_list else ''
        )

    # Clean up HTML and robot message from description
    if 'description' in df_selected.columns:
        df_selected['description'] = df_selected['description'].apply(
            lambda html: BeautifulSoup(html, 'html.parser').get_text() if html else ''
        )
        df_selected['description'] = df_selected['description'].str.replace(
            r'Please mention the word(.)*', "", regex=True
        )

    return df_selected


class RemoteOKScraper(BaseScraper):
    """Scraper for RemoteOK job board."""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.api_url = config.get('url', 'https://remoteok.com/api')

    def scrape_jobs(self, keywords: List[str]) -> pd.DataFrame:
        """Scrape jobs from RemoteOK API."""
        logger.info(f"Fetching data from RemoteOK: {self.api_url}")

        data = self.make_request(self.api_url)

        if not data:
            logger.warning("No data received from RemoteOK API")
            return pd.DataFrame(columns=self.df_columns)

        if isinstance(data, list) and len(data) > 1:
            return self.parse_job_data(data)
        elif isinstance(data, list) and len(data) <= 1:
            logger.warning("RemoteOK API returned an empty list of jobs")
            return pd.DataFrame(columns=self.df_columns)
        else:
            logger.error(f"Unexpected API response format. Expected a list, got {type(data)}")
            return pd.DataFrame(columns=self.df_columns)

    def parse_job_data(self, data: List[Dict]) -> pd.DataFrame:
        """Parse RemoteOK API response into standardized DataFrame."""
        # The RemoteOK API returns a list. The first item is a "legal notice" or API info.
        # Actual job listings start from the second item.
        if data[0].get("legal") is not None:
            logger.info(f"RemoteOK Legal Notice: {data[0].get('legal')}")
            job_list = data[1:]
        else:
            logger.warning("First element does not appear to be metadata. Processing all elements as jobs.")
            job_list = data

        if not job_list:
            return pd.DataFrame(columns=self.df_columns)

        # Use pandas.json_normalize to flatten the JSON structures
        df = pd.json_normalize(job_list)

        # Define the columns we are interested in
        desired_columns = [
            'id', 'url', 'company', 'position', 'tags', 'location',
            'description', 'salary_min', 'salary_max', 'epoch'
        ]

        # Define the keywords to look for in job titles
        keywords_pattern = 'analy|data|machine learning|intelligence'

        # Select only the desired columns that are actually present
        columns_to_select = [col for col in desired_columns if col in df.columns]

        if not columns_to_select:
            logger.warning("None of the desired columns were found in RemoteOK API response")
            return pd.DataFrame(columns=self.df_columns)

        # Filter jobs based on keywords in position or tags
        mask = (df['position'].str.contains(keywords_pattern, case=False, na=False) |
                df['tags'].str.contains(keywords_pattern, case=False, na=False))

        df_selected = df[columns_to_select][mask].copy()

        if df_selected.empty:
            logger.info("No data jobs found in RemoteOK listings")
            return pd.DataFrame(columns=self.df_columns)

        # Data transformations
        df_selected = _transform_data(df_selected, df)

        # Rename columns to match standard schema
        column_mapping = {
            'epoch': 'pubDate',
            'salary_min': 'salaryMin',
            'salary_max': 'salaryMax'
        }
        df_selected = df_selected.rename(columns=column_mapping)

        # Add source identifier
        df_selected['source'] = 'Remote OK'

        # Standardize DataFrame
        return self.standardize_dataframe(df_selected)

