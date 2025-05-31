"""
Jobicy job board scraper implementation.
"""

import pandas as pd
from bs4 import BeautifulSoup
from typing import List, Dict
import logging

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


def _transform_data(df_selected: pd.DataFrame) -> pd.DataFrame:
    """Apply Jobicy-specific data transformations."""
    # Convert 'pubDate' to datetime objects
    if 'pubDate' in df_selected.columns:
        df_selected['pubDate'] = df_selected['pubDate'].apply(
            lambda date: pd.to_datetime(date[:10], format='%Y-%m-%d', errors='coerce') if date else None
        )

    # Replace 'Any' in 'jobLevel' with an empty string for uniformity
    if 'jobLevel' in df_selected.columns:
        df_selected['jobLevel'] = df_selected['jobLevel'].replace('Any', '', regex=False)

    # Convert 'jobIndustry' list into a comma-separated string
    if 'jobIndustry' in df_selected.columns:
        df_selected['jobIndustry'] = df_selected['jobIndustry'].apply(
            lambda industries: ', '.join(industries).replace(' &amp;', ',') if isinstance(industries,
                                                                                          list) and industries else ''
        )

    # Convert 'jobType' list into a comma-separated string
    if 'jobType' in df_selected.columns:
        df_selected['jobType'] = df_selected['jobType'].apply(
            lambda job_type: ', '.join(job_type) if isinstance(job_type, list) and job_type else ''
        )

    # Clean up HTML from jobDescription
    if 'jobDescription' in df_selected.columns:
        df_selected['jobDescription'] = df_selected['jobDescription'].apply(
            lambda html: BeautifulSoup(html, 'html.parser').get_text() if html else ''
        )

    return df_selected


class JobicyScraper(BaseScraper):
    """Scraper for Jobicy job board."""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.api_url = config.get('url', 'https://jobicy.com/api/v2/remote-jobs')

    def scrape_jobs(self, keywords: List[str]) -> pd.DataFrame:
        """Scrape jobs from Jobicy API using multiple keywords."""
        logger.info(f"Fetching data from Jobicy: {self.api_url}")

        consolidated_data = {'jobs': []}

        # Fetch jobs for each keyword
        for keyword in keywords:
            logger.info(f"Fetching Jobicy jobs for keyword: {keyword}")

            params = {'tag': keyword}
            data = self.make_request(self.api_url, params=params)

            if not data:
                logger.warning(f"No data received from Jobicy API for keyword: {keyword}")
                continue

            if isinstance(data, dict) and len(data) > 0:
                consolidated_data['friendlyNotice'] = data.get('friendlyNotice', '')
                job_list = data.get('jobs', [])
                consolidated_data['jobs'].extend(job_list)
                logger.info(f"Found {len(job_list)} jobs for keyword '{keyword}'")
            elif isinstance(data, dict) and len(data) == 0:
                logger.info(f"Jobicy found no '{keyword}' jobs")
            else:
                logger.error(f"Unexpected API response format. Expected a dict, got {type(data)}")

        if not consolidated_data['jobs']:
            logger.warning("No jobs found from Jobicy for any keywords")
            return pd.DataFrame(columns=self.df_columns)

        return self.parse_job_data(consolidated_data)

    def parse_job_data(self, data: Dict) -> pd.DataFrame:
        """Parse Jobicy API response into standardized DataFrame."""
        friendly_notice = data.get('friendlyNotice', '')
        if friendly_notice:
            logger.info(f"Jobicy notice: {friendly_notice}")

        job_list = data.get('jobs', [])

        if not job_list:
            logger.warning("No job data provided from Jobicy")
            return pd.DataFrame(columns=self.df_columns)

        logger.info(f"Normalizing {len(job_list)} Jobicy job entries into DataFrame")

        # Use pandas.json_normalize to flatten the JSON structures
        df = pd.json_normalize(job_list)

        # Define the columns we are interested in
        desired_columns = [
            'id', 'url', 'companyName', 'jobTitle', 'jobIndustry', 'jobType',
            'jobGeo', 'jobLevel', 'jobDescription', 'pubDate', 'tags',
            'location', 'salaryMin', 'salaryMax', 'salaryCurrency', 'salaryPeriod'
        ]

        # Select only the desired columns that are actually present
        columns_to_select = [col for col in desired_columns if col in df.columns]

        if not columns_to_select:
            logger.warning("None of the desired columns were found in Jobicy API response")
            return pd.DataFrame(columns=self.df_columns)

        # Remove duplicates that may have been introduced by calling the API with multiple keywords
        df_selected = df[columns_to_select].drop_duplicates(subset=['id'])

        if df_selected.empty:
            logger.info("No unique jobs found in Jobicy listings after deduplication")
            return pd.DataFrame(columns=self.df_columns)

        # Data transformations
        df_selected = _transform_data(df_selected)

        # Rename columns to match standard schema
        column_mapping = {
            'companyName': 'company',
            'jobTitle': 'position',
            'jobIndustry': 'industry',
            'jobGeo': 'location',
            'jobDescription': 'description',
            'salaryCurrency': 'currency'
        }
        df_selected = df_selected.rename(columns=column_mapping)

        # Add source identifier
        df_selected['source'] = 'Jobicy'

        # Standardize DataFrame
        return self.standardize_dataframe(df_selected)

