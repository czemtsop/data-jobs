"""
Base scraper class and common utilities for job data collection.
"""

from abc import ABC, abstractmethod
from datetime import date
import requests
import pandas as pd
from typing import List, Dict, Optional
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_default_values() -> Dict:
    """Return default values for DataFrame columns."""
    return {
        'id': 0,
        'url': '',
        'company': '',
        'position': '',
        'description': '',
        'location': '',
        'pubDate': pd.to_datetime(date.today()),
        'salaryMin': 0,
        'salaryMax': 0,
        'industry': '',
        'jobType': '',
        'jobLevel': '',
        'tags': '',
        'currency': '',
        'salaryPeriod': ''
    }


class BaseScraper(ABC):
    """Abstract base class for job board scrapers."""

    def __init__(self, config: Dict):
        self.config = config
        self.timeout = config.get('timeout', 10)
        self.rate_limit_delay = config.get('rate_limit_delay', 2)
        self.session = requests.Session()

        # Standard DataFrame columns for all scrapers
        self.df_columns = [
            'id', 'url', 'company', 'position', 'description', 'location',
            'pubDate', 'salaryMin', 'salaryMax', 'industry', 'jobType',
            'jobLevel', 'tags', 'currency', 'salaryPeriod', 'source'
        ]

    @abstractmethod
    def scrape_jobs(self, keywords: List[str]) -> pd.DataFrame:
        """Scrape jobs from the specific job board."""
        pass

    @abstractmethod
    def parse_job_data(self, raw_data: Dict) -> pd.DataFrame:
        """Parse raw API response into standardized DataFrame."""
        pass

    def make_request(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make HTTP request with error handling and rate limiting."""
        try:
            # Rate limiting
            time.sleep(self.rate_limit_delay)

            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()

            return response.json()

        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error occurred while trying to reach {url}")
            return None
        except requests.exceptions.TooManyRedirects:
            logger.error(f"Too many redirects while trying to reach {url}")
            return None
        except requests.exceptions.Timeout:
            logger.error(f"Request to {url} timed out")
            return None
        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP error occurred: {http_err} - Status Code: {response.status_code}")
            return None
        except requests.exceptions.RequestException as req_err:
            logger.error(f"An error occurred while fetching data from API: {req_err}")
            return None
        except ValueError as json_err:
            logger.error(f"Could not decode JSON response: {json_err}")
            return None

    def standardize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure DataFrame has all required columns with proper types."""
        # Add missing columns with default values
        default_values = get_default_values()
        for col in self.df_columns:
            if col not in df.columns:
                df[col] = default_values[col]

        # Reorder columns
        df = df[self.df_columns]

        # Fill NaN values
        return df.fillna(default_values)


class ScraperFactory:
    """Factory class to create appropriate scraper instances."""

    @staticmethod
    def create_scraper(scraper_type: str, config: Dict) -> BaseScraper:
        """Create scraper instance based on type."""
        from .remoteok_scraper import RemoteOKScraper
        from .jobicy_scraper import JobicyScraper

        scrapers = {
            'remoteok': RemoteOKScraper,
            'jobicy': JobicyScraper,
        }

        if scraper_type not in scrapers:
            raise ValueError(f"Unknown scraper type: {scraper_type}")

        return scrapers[scraper_type](config)