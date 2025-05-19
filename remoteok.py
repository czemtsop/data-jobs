import pandas as pd  # For data manipulation and creating DataFrames
import requests  # For making HTTP requests to the API
from bs4 import BeautifulSoup as bs
import matplotlib.pyplot as plt
from collections import Counter
from wordcloud import WordCloud, STOPWORDS


def fetch_remoteok_jobs_from_api():
    """
    Fetches job listings from the RemoteOK API.

    The RemoteOK API returns a list. The first element is often a legal notice or API information,
    so we skip it to get to the actual job listings.

    Returns:
        data: A list of job dictionaries if successful, None otherwise.
    """
    api_url = "https://remoteok.com/api"
    print(f"Attempting to fetch data from: {api_url}")
    try:
        response = requests.get(api_url, timeout=10)  # Added timeout for robustness
        response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)

        data = response.json()

        # The RemoteOK API returns a list. The first item is a "legal notice" or API info.
        # Actual job listings start from the second item.
        if isinstance(data, list) and len(data) > 0:
            if data[0].get("legal") is not None:
                print(f"Skipping the first element (meta-data/legal): {data[0].get('legal')}")
                return data[1:]  # Return the rest of the list
            else:
                # If the first element doesn't look like metadata, perhaps the API structure changed.
                # For now, we'll assume it's all job data.
                print("First element does not appear to be metadata. Processing all elements as data-jobs.")
                return data
        elif isinstance(data, list) and len(data) == 0:
            print("API returned an empty list of data-jobs.")
            return []
        else:
            print(f"Unexpected API response format. Expected a list, got {type(data)}.")
            return None

    except requests.exceptions.Timeout:
        print(f"Error: Request to {api_url} timed out.")
        return None
    except requests.exceptions.HTTPError as http_err:
        print(f"Error: HTTP error occurred: {http_err} - Status Code: {response.status_code}")
        return None
    except requests.exceptions.RequestException as req_err:
        print(f"Error: An error occurred while fetching data from API: {req_err}")
        return None
    except ValueError as json_err:  # Includes json.JSONDecodeError
        print(f"Error: Could not decode JSON response: {json_err}")
        return None


    except requests.exceptions.Timeout:
        print(f"Error: Request to {api_url} timed out.")
        return None
    except requests.exceptions.HTTPError as http_err:
        print(f"Error: HTTP error occurred: {http_err} - Status Code: {response.status_code}")
        return None
    except requests.exceptions.RequestException as req_err:
        print(f"Error: An error occurred while fetching data from API: {req_err}")
        return None
    except ValueError as json_err:  # Includes json.JSONDecodeError
        print(f"Error: Could not decode JSON response: {json_err}")
        return None


def parse_jobs_to_structured_dataframe(job_list):
    """
    Parses a list of job dictionaries (from API) into a pandas DataFrame.
    Selects relevant columns and performs basic data cleaning/transformation.

    Args:
        job_list (list): A list of dictionaries, where each dictionary represents a job.

    Returns:
        pandas.DataFrame: A DataFrame containing structured job data, or an empty DataFrame if input is invalid.
    """
    if not job_list or not isinstance(job_list, list):
        print("No job data provided or data is not in list format. Returning empty DataFrame.")
        return pd.DataFrame()

    print(f"Normalizing {len(job_list)} job entries into a DataFrame...")
    # Use pandas.json_normalize to flatten the JSON structures.
    df = pd.json_normalize(job_list)

    # --- Data Cleaning and Transformation ---

    # Define the columns we are interested in.
    desired_columns = [
        'id', 'company', 'position', 'tags', 'location', 'salary_min', 'salary_max'
    ]
    # Define the keywords to look for in job titles
    keywords = 'analy|data|machine learning|intelligence'

    # Select only the desired columns that are actually present in the DataFrame
    # This makes the script more robust to changes in the API response
    columns_to_select = [col for col in desired_columns if col in df.columns]

    if not columns_to_select:
        print("None of the desired columns were found in the API response. Returning empty DataFrame.")
        return pd.DataFrame()

    df_selected = df[columns_to_select][df['position'].str.contains(keywords, case=False) |
                                        df['tags'].str.contains(keywords,
                                                                case=False)].copy()  # Use .copy() to avoid SettingWithCopyWarning

    # Convert 'epoch' to datetime objects
    if 'epoch' in df.columns:
        # Ensure 'epoch' is numeric, coercing errors to NaT (Not a Time)
        df_selected['epoch'] = pd.to_datetime(df['epoch'], unit='s', errors='coerce')

    # Convert 'tags' list into a comma-separated string for easier use in SQL/CSV.
    if 'tags' in df_selected.columns:
        df_selected['tags_string'] = df_selected['tags'].apply(
            lambda tags_list: ', '.join(tags_list) if isinstance(tags_list, list) and tags_list else None
        )

    # Clean up HTML and robot message from description
    if 'description' in df.columns:
        df_selected['description'] = df['description'].apply(
            lambda html: bs(html, 'html.parser').get_text()
        )
        df_selected['description'] = df_selected['description'].str.replace(r'Please mention the word(.)*', "",
                                                                            regex=True)

    return df_selected


def analyze_job_data(job_postings):
    """Performs basic analysis on the fetched job listings."""

    all_descriptions = ", ".join(job_postings.description).lower()
    keywords = all_descriptions.split()
    common_keywords = Counter(keywords).most_common(20) # Get the top 20 most frequent words

    print("\nTop 20 most common keywords in job descriptions:")
    for keyword, count in common_keywords:
        if keyword not in STOPWORDS: # Basic stop word removal
            print(f"- {keyword}: {count}")

    # Generate word cloud using tags on job postings
    tags = ", ".join(job_postings.tags_string).lower()

    wordcloud = WordCloud().generate(tags)
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis("off")
    plt.show()

def main():
    """
    Main function to orchestrate the data fetching, parsing, and loading process.
    """
    print("--- Starting RemoteOK Job Data Pipeline ---")

    # Step 1: Fetch job data from the API
    raw_job_data = fetch_remoteok_jobs_from_api()

    if raw_job_data is None:
        print("Failed to fetch job data from remoteok. Exiting pipeline.")
        return

    if not raw_job_data:
        print("No job listings fetched from the API. Exiting pipeline.")
        return

    print(f"Successfully fetched {len(raw_job_data)} raw job entries.")

    # Step 2: Parse and transform data into a pandas DataFrame
    jobs_dataframe = parse_jobs_to_structured_dataframe(raw_job_data)

    if jobs_dataframe.empty:
        print("DataFrame creation failed or resulted in an empty DataFrame. Exiting pipeline.")
        return

    print("\n--- DataFrame Information ---")
    jobs_dataframe.info()

    analyze_job_data(jobs_dataframe)


if __name__ == "__main__":
    # This block ensures that main() is called only when the script is executed directly
    main()