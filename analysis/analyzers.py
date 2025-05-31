"""
Statistical analysis modules for job postings data.
Provides comprehensive analysis capabilities for data career job postings.
"""

from collections import Counter
import pandas as pd
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

# Ensure required NLTK data is available
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
    nltk.download('punkt_tab')

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

# Define the stopwords for text processing
STOPWORDS_SET = set(stopwords.words('english'))
STOPWORDS_SET.update(['across', 'help', 'skills', 'will'])  # Add custom stopwords


def analyze_salary_trends_by_location(df):
    """
    Analyzes average salary trends across locations.

    Args:
        df (pd.DataFrame): DataFrame containing job postings with salary and location data

    Returns:
        pd.DataFrame: Grouped salary data by location
    """
    # Filter out rows with missing or zero salary and location
    salary_df = df[
        (df['salaryMin'] > 0) &
        (df['salaryMax'] > 0) &
        (df['location'].str.strip() != '')
    ].copy()

    if salary_df.empty:
        print("No salary/location data available for analysis.")
        return pd.DataFrame()

    # Group by location and calculate average salaries
    grouped = salary_df.groupby('location')[['salaryMin', 'salaryMax']].mean()
    grouped = grouped.sort_values('salaryMax', ascending=False)

    return grouped


def analyze_job_types(job_postings):
    """
    Analyzes distribution of job types/categories.

    Args:
        job_postings (pd.DataFrame): DataFrame containing job postings

    Returns:
        pd.Series: Count of jobs by type/category
    """
    if 'jobType' in job_postings.columns:
        return job_postings['jobType'].value_counts()
    elif 'category' in job_postings.columns:
        return job_postings['category'].value_counts()
    else:
        print("No job type/category data available for analysis.")
        return pd.Series()


def analyze_company_sizes(job_postings):
    """
    Analyzes distribution of company sizes.

    Args:
        job_postings (pd.DataFrame): DataFrame containing job postings

    Returns:
        pd.Series: Count of jobs by company size
    """
    if 'companySize' in job_postings.columns:
        return job_postings['companySize'].value_counts()
    else:
        print("No company size data available for analysis.")
        return pd.Series()


def get_summary_stats(job_postings):
    """
    Generates summary statistics for the job postings dataset.

    Args:
        job_postings (pd.DataFrame): DataFrame containing job postings

    Returns:
        dict: Dictionary containing summary statistics
    """
    stats = {
        'total_jobs': len(job_postings),
        'unique_companies': job_postings['company'].nunique() if 'company' in job_postings.columns else 0,
        'unique_locations': job_postings['location'].nunique() if 'location' in job_postings.columns else 0,
        'jobs_with_salary': len(job_postings[(job_postings['salaryMin'] > 0) & (job_postings['salaryMax'] > 0)]) if 'salaryMin' in job_postings.columns else 0,
        'date_range': {
            'earliest': job_postings['datePosted'].min() if 'datePosted' in job_postings.columns else None,
            'latest': job_postings['datePosted'].max() if 'datePosted' in job_postings.columns else None
        }
    }

    return stats


class JobAnalyzer:
    """Main analyzer class for job postings data analysis."""

    def __init__(self, local_stopwords=None):
        """Initialize the analyzer with optional custom stopwords."""
        self.stopwords = local_stopwords or STOPWORDS_SET

    def analyze_keywords(self, job_postings, top_n=20):
        """
        Analyzes most common keywords in job descriptions.

        Args:
            job_postings (pd.DataFrame): DataFrame containing job postings
            top_n (int): Number of top keywords to return

        Returns:
            list: List of tuples (keyword, count) for top keywords
        """
        if job_postings.empty or 'description' not in job_postings.columns:
            print("No job descriptions available for keyword analysis.")
            return []

        all_descriptions = ", ".join(job_postings.description.fillna("")).lower()
        tokens = word_tokenize(all_descriptions)
        keywords = [word for word in tokens if word.isalpha() and word not in self.stopwords]
        common_keywords = Counter(keywords).most_common(top_n)

        return common_keywords


def analyze_job_data(job_postings):
    """
    Performs comprehensive analysis on job postings data.
    Legacy function maintained for backward compatibility.

    Args:
        job_postings (pd.DataFrame): DataFrame containing job postings

    Returns:
        dict: Analysis results including keywords and summary stats
    """
    analyzer = JobAnalyzer()

    # Keyword analysis
    common_keywords = analyzer.analyze_keywords(job_postings)

    print("\nTop 20 most common keywords in job descriptions:")
    for keyword, count in common_keywords:
        print(f"- {keyword}: {count}")

    # Summary statistics
    stats = get_summary_stats(job_postings)

    print(f"\n--- Dataset Summary ---")
    print(f"Total jobs: {stats['total_jobs']}")
    print(f"Unique companies: {stats['unique_companies']}")
    print(f"Unique locations: {stats['unique_locations']}")
    print(f"Jobs with salary info: {stats['jobs_with_salary']}")

    return {
        'keywords': common_keywords,
        'stats': stats,
        'salary_by_location': analyze_salary_trends_by_location(job_postings)
    }