"""
Chart and report generators for job postings data visualization.
Provides comprehensive visualization capabilities for data career job postings analysis.
"""

import numpy as np
import seaborn as sns
from matplotlib import pyplot as plt
from os import path
from PIL import Image
from wordcloud import WordCloud
import pandas as pd

from analysis.analyzers import analyze_job_types, get_summary_stats

# Set up plotting style
plt.style.use('default')
sns.set_palette("husl")


def create_wordcloud(text, mask_image_path=None, max_words=30,
                     width=800, height=400, background_color='white'):
    """
    Generates a word cloud from the provided text.

    Args:
        text (str): The text to generate the word cloud from.
        mask_image_path (str): Path to an image file to use as a mask for the word cloud.
        max_words (int): Maximum number of words to display
        width (int): Width of the word cloud
        height (int): Height of the word cloud
        background_color (str): Background color of the word cloud

    Returns:
        WordCloud: A WordCloud object.
    """
    mask_array = None

    if mask_image_path and path.exists(mask_image_path):
        try:
            mask = Image.open(mask_image_path)
            mask = mask.convert("L")  # Convert to grayscale
            mask_array = np.array(mask)
        except Exception as e:
            print(f"Warning: Could not load mask image: {e}")

    # Import stopwords from analysis module
    from analysis.analyzers import STOPWORDS_SET

    wc = WordCloud(
        width=width,
        height=height,
        background_color=background_color,
        max_words=max_words,
        stopwords=STOPWORDS_SET,
        mask=mask_array,
        contour_color='steelblue',
        contour_width=1
    ).generate(text)

    return wc


def create_summary_dashboard(job_postings, save_path=None):
    """
    Creates a comprehensive dashboard with multiple visualizations.

    Args:
        job_postings (pd.DataFrame): DataFrame containing job postings
        save_path (str): Optional path to save the dashboard
    """
    from analysis.analyzers import JobAnalyzer

    analyzer = JobAnalyzer()

    # Create a figure with subplots
    fig, axes = plt.subplots(2, 2, figsize=(20, 16))
    fig.suptitle('Job Market Analysis Dashboard', fontsize=20, y=0.98)

    # 1. Keywords bar chart
    keywords = analyzer.analyze_keywords(job_postings, top_n=10)
    if keywords:
        keywords_names = [item[0] for item in keywords]
        keywords_counts = [item[1] for item in keywords]
        axes[0, 0].barh(range(len(keywords_names)), keywords_counts)
        axes[0, 0].set_yticks(range(len(keywords_names)))
        axes[0, 0].set_yticklabels(keywords_names)
        axes[0, 0].set_title('Top 10 Keywords in Job Descriptions')
        axes[0, 0].set_xlabel('Frequency')
        axes[0, 0].grid(axis='x', alpha=0.3)

    # 2. Job types distribution
    job_types = analyze_job_types(job_postings)
    if not job_types.empty:
        job_types.head(8).plot(kind='pie', ax=axes[0, 1], autopct='%1.1f%%')
        axes[0, 1].set_title('Job Types Distribution')
        axes[0, 1].set_ylabel('')

    # 3. Salary trends by location (top 8)
    if not job_postings.empty:
        job_postings.head(8)[['salaryMin', 'salaryMax']].plot(kind='bar', ax=axes[1, 0])
        axes[1, 0].set_title('Average Salary Ranges by Location (Top 8)')
        axes[1, 0].set_ylabel('Salary (USD)')
        axes[1, 0].set_xlabel('Location')
        axes[1, 0].tick_params(axis='x', rotation=45)
        axes[1, 0].legend(['Min Salary', 'Max Salary'])
        axes[1, 0].grid(axis='y', alpha=0.3)

    # 4. Summary statistics as text
    stats = get_summary_stats(job_postings)
    stats_text = f"""
    Dataset Summary:

    Total Jobs: {stats['total_jobs']:,}
    Unique Companies: {stats['unique_companies']:,}
    Unique Locations: {stats['unique_locations']:,}
    Jobs with Salary Info: {stats['jobs_with_salary']:,}

    Salary Coverage: {(stats['jobs_with_salary'] / stats['total_jobs'] * 100):.1f}%
    """

    axes[1, 1].text(0.1, 0.5, stats_text, fontsize=14, verticalalignment='center',
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue", alpha=0.7))
    axes[1, 1].set_xlim(0, 1)
    axes[1, 1].set_ylim(0, 1)
    axes[1, 1].axis('off')
    axes[1, 1].set_title('Dataset Statistics')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    plt.show()


def plot_salary_trends_by_location(salary_data, title="Average Salary Ranges by Location",
                                   save_path=None, top_n=15):
    """
    Plots salary trends by location.

    Args:
        salary_data (pd.DataFrame): Grouped salary data by location
        title (str): Title for the plot
        save_path (str): Optional path to save the plot
        top_n (int): Number of top locations to display
    """
    if salary_data.empty:
        print("No salary data available for visualization.")
        return

    # Limit to top N locations for readability
    plot_data = salary_data.head(top_n)

    plt.figure(figsize=(14, 8))
    plot_data[['salaryMin', 'salaryMax']].plot(kind='bar', figsize=(14, 8))
    plt.title(title, fontsize=16, pad=20)
    plt.ylabel('Salary (USD)', fontsize=12)
    plt.xlabel('Location', fontsize=12)
    plt.xticks(rotation=45, ha='right')
    plt.legend(['Minimum Salary', 'Maximum Salary'])
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    plt.show()


def plot_keywords_bar_chart(keywords_data, title="Top Keywords in Job Descriptions",
                            save_path=None, top_n=20):
    """
    Creates a horizontal bar chart of top keywords.

    Args:
        keywords_data (list): List of (keyword, count) tuples
        title (str): Title for the plot
        save_path (str): Optional path to save the plot
        top_n (int): Number of top keywords to display
    """
    if not keywords_data:
        print("No keyword data available for visualization.")
        return

    # Prepare data
    keywords = [item[0] for item in keywords_data[:top_n]]
    counts = [item[1] for item in keywords_data[:top_n]]

    plt.figure(figsize=(12, 8))
    plt.barh(range(len(keywords)), counts)
    plt.yticks(range(len(keywords)), keywords)
    plt.xlabel('Frequency', fontsize=12)
    plt.title(title, fontsize=16, pad=20)
    plt.grid(axis='x', alpha=0.3)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    plt.show()


class JobVisualizer:
    """Main visualizer class for creating charts and reports from job data."""

    def __init__(self, figsize=(12, 6), style='seaborn-v0_8'):
        """Initialize the visualizer with default settings."""
        self.figsize = figsize
        try:
            plt.style.use(style)
        except OSError:
            plt.style.use('default')

    def plot_wordcloud(self, text, mask_image_path=None, title="Word Cloud", save_path=None):
        """
        Creates and displays a word cloud plot.

        Args:
            text (str): Text to generate word cloud from
            mask_image_path (str): Optional path to mask image
            title (str): Title for the plot
            save_path (str): Optional path to save the plot
        """
        wordcloud = create_wordcloud(text, mask_image_path)

        plt.figure(figsize=self.figsize)
        plt.imshow(wordcloud, interpolation='bilinear')
        plt.axis("off")
        plt.title(title, fontsize=16, pad=20)
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')

        plt.show()

    def plot_job_distribution(self, job_counts, title="Job Distribution",
                              plot_type='bar', save_path=None, top_n=10):
        """
        Plots distribution of jobs by category/type.

        Args:
            job_counts (pd.Series): Count data for jobs
            title (str): Title for the plot
            plot_type (str): Type of plot ('bar', 'pie', 'horizontal_bar')
            save_path (str): Optional path to save the plot
            top_n (int): Number of top categories to display
        """
        if job_counts.empty:
            print("No job distribution data available for visualization.")
            return

        plot_data = job_counts.head(top_n)

        plt.figure(figsize=self.figsize)

        if plot_type == 'bar':
            plot_data.plot(kind='bar')
            plt.xticks(rotation=45, ha='right')
        elif plot_type == 'horizontal_bar':
            plot_data.plot(kind='barh')
        elif plot_type == 'pie':
            plt.figure(figsize=(10, 10))
            plot_data.plot(kind='pie', autopct='%1.1f%%')
            plt.ylabel('')

        plt.title(title, fontsize=16, pad=20)
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')

        plt.show()

