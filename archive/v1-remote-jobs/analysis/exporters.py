"""
Output formatting and delivery modules for job postings analysis results.
Handles exporting analysis results to various formats including CSV, JSON, Excel, and HTML reports.
"""

import json
import pandas as pd
from datetime import datetime, date
from pathlib import Path


def _get_timestamp():
    """Get current timestamp for file naming."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


class JobDataExporter:
    """Main exporter class for job analysis results."""

    def __init__(self, output_dir="data/outputs"):
        """
        Initialize the exporter with output directory.

        Args:
            output_dir (str): Directory to save exported files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_to_csv(self, data, filename=None, include_timestamp=True):
        """
        Export DataFrame to CSV format.

        Args:
            data (pd.DataFrame): Data to export
            filename (str): Custom filename (optional)
            include_timestamp (bool): Whether to include timestamp in filename

        Returns:
            str: Path to exported file
        """
        if filename is None:
            filename = "job_analysis_data"

        if include_timestamp:
            filename = f"{filename}_{_get_timestamp()}"

        filepath = self.output_dir / f"{filename}.csv"

        try:
            data.to_csv(filepath, index=False)
            print(f"Data exported to CSV: {filepath}")
            return str(filepath)
        except Exception as e:
            print(f"Error exporting to CSV: {e}")
            return None

    def export_to_json(self, data, filename=None, include_timestamp=True):
        """
        Export data to JSON format.

        Args:
            data (dict or pd.DataFrame): Data to export
            filename (str): Custom filename (optional)
            include_timestamp (bool): Whether to include timestamp in filename

        Returns:
            str: Path to exported file
        """
        if filename is None:
            filename = "job_analysis_results"

        if include_timestamp:
            filename = f"{filename}_{_get_timestamp()}"

        filepath = self.output_dir / f"{filename}.json"

        try:
            # Convert DataFrame to dict if necessary
            if isinstance(data, pd.DataFrame):
                export_data = data.to_dict('records')
            else:
                export_data = data

            # Handle datetime objects in JSON serialization
            def json_serializer(obj):
                if isinstance(obj, (datetime, date)):
                    return obj.isoformat()
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2, default=json_serializer)

            print(f"Data exported to JSON: {filepath}")
            return str(filepath)
        except Exception as e:
            print(f"Error exporting to JSON: {e}")
            return None

    def export_to_excel(self, data_dict, filename=None, include_timestamp=True):
        """
        Export multiple DataFrames to Excel with separate sheets.

        Args:
            data_dict (dict): Dictionary with sheet names as keys and DataFrames as values
            filename (str): Custom filename (optional)
            include_timestamp (bool): Whether to include timestamp in filename

        Returns:
            str: Path to exported file
        """
        if filename is None:
            filename = "job_analysis_report"

        if include_timestamp:
            filename = f"{filename}_{_get_timestamp()}"

        filepath = self.output_dir / f"{filename}.xlsx"

        try:
            with pd.ExcelWriter(filepath, engine='xlsxwriter') as writer:
                if isinstance(data_dict, pd.DataFrame):
                    # Single DataFrame
                    data_dict.to_excel(writer, sheet_name='Analysis', index=False)
                else:
                    # Multiple DataFrames
                    for sheet_name, df in data_dict.items():
                        if isinstance(df, pd.DataFrame):
                            df.to_excel(writer, sheet_name=sheet_name, index=False)
                        else:
                            # Convert other data types to DataFrame
                            temp_df = pd.DataFrame([df] if isinstance(df, dict) else df)
                            temp_df.to_excel(writer, sheet_name=sheet_name, index=False)

            print(f"Data exported to Excel: {filepath}")
            return str(filepath)
        except Exception as e:
            print(f"Error exporting to Excel: {e}")
            return None

    def export_summary_report(self, analysis_results, filename=None):
        """
        Export a comprehensive summary report in multiple formats.

        Args:
            analysis_results (dict): Complete analysis results
            filename (str): Base filename (optional)

        Returns:
            dict: Paths to exported files
        """
        if filename is None:
            filename = "job_market_analysis_report"

        timestamp = _get_timestamp()
        filename_with_timestamp = f"{filename}_{timestamp}"

        exported_files = {}

        # Export summary statistics to JSON
        if 'stats' in analysis_results:
            json_path = self.export_to_json(
                analysis_results['stats'],
                f"{filename_with_timestamp}_summary",
                include_timestamp=False
            )
            exported_files['summary_json'] = json_path

        # Export keywords to CSV
        if 'keywords' in analysis_results:
            keywords_df = pd.DataFrame(
                analysis_results['keywords'],
                columns=['Keyword', 'Frequency']
            )
            csv_path = self.export_to_csv(
                keywords_df,
                f"{filename_with_timestamp}_keywords",
                include_timestamp=False
            )
            exported_files['keywords_csv'] = csv_path

        # Export salary data to CSV
        if 'salary_by_location' in analysis_results and not analysis_results['salary_by_location'].empty:
            salary_df = analysis_results['salary_by_location'].reset_index()
            csv_path = self.export_to_csv(
                salary_df,
                f"{filename_with_timestamp}_salary_trends",
                include_timestamp=False
            )
            exported_files['salary_csv'] = csv_path

        # Create comprehensive Excel report
        excel_data = {}
        if 'keywords' in analysis_results:
            excel_data['Keywords'] = pd.DataFrame(
                analysis_results['keywords'][:20],
                columns=['Keyword', 'Frequency']
            )

        if 'salary_by_location' in analysis_results and not analysis_results['salary_by_location'].empty:
            excel_data['Salary_Trends'] = analysis_results['salary_by_location'].reset_index()

        if 'stats' in analysis_results:
            stats_data = []
            for key, value in analysis_results['stats'].items():
                if key != 'date_range':
                    stats_data.append({'Metric': key, 'Value': value})
            excel_data['Summary_Stats'] = pd.DataFrame(stats_data)

        if excel_data:
            excel_path = self.export_to_excel(
                excel_data,
                filename_with_timestamp,
                include_timestamp=False
            )
            exported_files['excel_report'] = excel_path

        return exported_files

    def export_html_report(self, analysis_results, filename=None):
        """
        Generate an HTML report with embedded visualizations.

        Args:
            analysis_results (dict): Analysis results
            filename (str): Custom filename (optional)

        Returns:
            str: Path to exported HTML file
        """
        if filename is None:
            filename = f"job_analysis_report_{_get_timestamp()}"

        filepath = self.output_dir / f"{filename}.html"

        # Create HTML content
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Job Market Analysis Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
                .section {{ margin: 20px 0; }}
                .stats-table {{ border-collapse: collapse; width: 100%; }}
                .stats-table th, .stats-table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                .stats-table th {{ background-color: #f2f2f2; }}
                .keywords-list {{ columns: 2; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Job Market Analysis Report</h1>
                <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            
            <div class="section">
                <h2>Dataset Summary</h2>
                <table class="stats-table">
        """

        # Add summary statistics
        if 'stats' in analysis_results:
            for key, value in analysis_results['stats'].items():
                if key != 'date_range':
                    html_content += f"<tr><td>{key.replace('_', ' ').title()}</td><td>{value:,}</td></tr>"

        html_content += """
                </table>
            </div>
            
            <div class="section">
                <h2>Top Keywords</h2>
                <div class="keywords-list">
        """

        # Add keywords
        if 'keywords' in analysis_results:
            for keyword, count in analysis_results['keywords'][:20]:
                html_content += f"<p><strong>{keyword}</strong>: {count}</p>"

        html_content += """
                </div>
            </div>
            
            <div class="section">
                <h2>Salary Analysis</h2>
        """

        # Add salary information
        if 'salary_by_location' in analysis_results and not analysis_results['salary_by_location'].empty:
            html_content += '<table class="stats-table"><tr><th>Location</th><th>Min Salary</th><th>Max Salary</th></tr>'
            for location, row in analysis_results['salary_by_location'].head(10).iterrows():
                html_content += f"<tr><td>{location}</td><td>${row['salaryMin']:,.0f}</td><td>${row['salaryMax']:,.0f}</td></tr>"
            html_content += '</table>'
        else:
            html_content += '<p>No salary data available for analysis.</p>'

        html_content += """
            </div>
        </body>
        </html>
        """

        try:
            with open(filepath, 'w') as f:
                f.write(html_content)

            print(f"HTML report exported: {filepath}")
            return str(filepath)
        except Exception as e:
            print(f"Error exporting HTML report: {e}")
            return None


def export_analysis_results(analysis_results, job_postings=None, output_format='all',
                          output_dir="data/outputs", filename=None):
    """
    Convenience function to export analysis results in specified format(s).

    Args:
        analysis_results (dict): Complete analysis results
        job_postings (pd.DataFrame): Original job postings data (optional)
        output_format (str): Format to export ('csv', 'json', 'excel', 'html', 'all')
        output_dir (str): Directory to save files
        filename (str): Base filename (optional)

    Returns:
        dict: Paths to exported files
    """
    exporter = JobDataExporter(output_dir)

    if output_format == 'all':
        # Export comprehensive report
        exported_files = exporter.export_summary_report(analysis_results, filename)

        # Add HTML report if job_postings is provided
        if job_postings is not None:
            html_path = exporter.export_html_report(analysis_results, filename)
            exported_files['html_report'] = html_path

        return exported_files

    elif output_format == 'csv':
        if 'keywords' in analysis_results:
            keywords_df = pd.DataFrame(
                analysis_results['keywords'],
                columns=['Keyword', 'Frequency']
            )
            return {'csv': exporter.export_to_csv(keywords_df, filename)}
        return None

    elif output_format == 'json':
        return {'json': exporter.export_to_json(analysis_results, filename)}

    elif output_format == 'excel':
        return {'excel': exporter.export_to_excel(analysis_results, filename)}

    elif output_format == 'html' and job_postings is not None:
        return {'html': exporter.export_html_report(analysis_results, filename)}

    else:
        print(f"Unsupported output format: {output_format}")
        return {}