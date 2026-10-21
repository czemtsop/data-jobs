"""
Main execution script for the Data Career Job Market Analysis project.
This script orchestrates the complete pipeline from data collection to analysis and reporting.
"""

from datetime import datetime
import sys
import os
import yaml

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scraper.coordinator import ScraperCoordinator
from analysis.analyzers import analyze_job_data
from analysis.visualizers import JobVisualizer, create_summary_dashboard
from analysis.exporters import export_analysis_results


def main():
    """
    Main function to orchestrate the complete data analysis pipeline.
    """
    print("🚀 Starting Data Career Job Market Analysis Pipeline")
    print("=" * 60)
    print(f"📅 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    with open('config/config.yaml', 'r') as file:
        config = yaml.safe_load(file)

    # Step 1: Data Collection
    print("\n🕷️ STEP 1: Data Collection")
    print("-" * 30)
    print("📡 Fetching job data from multiple sources...")

    try:
        scraper_coordinator = ScraperCoordinator(config)
        jobs_df = scraper_coordinator.fetch_all_jobs(['remoteok', 'jobicy'])

        if jobs_df.empty:
            print("❌ No job data retrieved. Please check your scrapers.")
            print("🔧 Troubleshooting tips:")
            print("   - Check your internet connection")
            print("   - Verify scraper configurations")
            print("   - Check if job board APIs are accessible")
            return

        print(f"✅ Successfully collected {len(jobs_df)} job postings!")
        print(f"📊 Dataset shape: {jobs_df.shape}")
        print(f"🏢 Unique companies: {jobs_df['company'].nunique() if 'company' in jobs_df.columns else 'N/A'}")
        print(f"🌍 Unique locations: {jobs_df['location'].nunique() if 'location' in jobs_df.columns else 'N/A'}")

    except Exception as ex:
        print(f"❌ Error during data collection: {ex}")
        return

    # Step 2: Data Analysis
    print("\n🔬 STEP 2: Data Analysis")
    print("-" * 30)
    print("🧮 Running comprehensive job market analysis...")

    try:
        # Perform main analysis
        analysis_results = analyze_job_data(jobs_df)

        if not analysis_results:
            print("⚠️ Analysis completed but no results generated")
            return

        print("✅ Analysis completed successfully!")

    except Exception as ex:
        print(f"❌ Error during analysis: {ex}")
        return

    # Step 3: Visualization
    print("\n🎨 STEP 3: Creating Visualizations")
    print("-" * 30)

    try:
        visualizer = JobVisualizer()

        # Create word cloud if tags are available
        if 'tags' in jobs_df.columns:
            print("🌟 Generating skills word cloud...")
            tags_text = ", ".join(jobs_df.tags.fillna("")).lower()
            if tags_text.strip():
                visualizer.plot_wordcloud(
                    tags_text,
                    title="Most In-Demand Skills & Technologies",
                    save_path="data/outputs/skills_wordcloud.png"
                )

        # Create comprehensive dashboard
        print("📊 Creating analysis dashboard...")
        create_summary_dashboard(
            jobs_df,
            save_path="data/outputs/job_market_dashboard.png"
        )

        print("✅ Visualizations created successfully!")

    except Exception as ex:
        print(f"⚠️ Warning: Some visualizations may have failed: {ex}")

    # Step 4: Export Results
    print("\n📤 STEP 4: Exporting Results")
    print("-" * 30)

    try:
        print("📦 Exporting analysis results in multiple formats...")

        exported_files = export_analysis_results(
            analysis_results,
            job_postings=jobs_df,
            output_format='all',
            filename='data_jobs_market_analysis'
        )

        print("\n📁 Files successfully exported:")
        for file_type, file_path in exported_files.items():
            if file_path:
                print(f"   📄 {file_type.replace('_', ' ').title()}: {file_path}")

        print("✅ All exports completed!")

    except Exception as ex:
        print(f"⚠️ Warning: Export may have failed: {ex}")

    # Step 5: Final Summary
    print("\n🎯 PIPELINE SUMMARY")
    print("=" * 60)

    if analysis_results and 'stats' in analysis_results:
        stats = analysis_results['stats']

        print(f"📊 Jobs Analyzed: {stats.get('total_jobs', 0):,}")
        print(f"🏢 Companies: {stats.get('unique_companies', 0):,}")
        print(f"🌍 Locations: {stats.get('unique_locations', 0):,}")
        print(f"💰 Jobs with Salary: {stats.get('jobs_with_salary', 0):,}")

        if stats.get('total_jobs', 0) > 0:
            salary_coverage = (stats.get('jobs_with_salary', 0) / stats.get('total_jobs', 1)) * 100
            print(f"📈 Salary Coverage: {salary_coverage:.1f}%")

        if analysis_results.get('keywords'):
            top_skill = analysis_results['keywords'][0][0]
            print(f"🔥 Top Skill: {top_skill}")

    print(f"\n📅 Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🚀 Ready for data-driven career insights!")
    print("=" * 60)

    # Provide next steps
    print("\n💡 NEXT STEPS:")
    print("   📓 Open 'analyze_jobs.ipynb' for interactive analysis")
    print("   📁 Check 'data/outputs/' for generated reports")
    print("   🔍 Explore exported files for detailed insights")


if __name__ == "__main__":
    """
    Entry point for the script execution.
    This ensures main() is called only when the script is run directly.
    """
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️ Analysis interrupted by user")
        print("👋 Thanks for using the Data Jobs Analysis pipeline!")
    except Exception as e:
        print(f"\n❌ Unexpected error occurred: {e}")
        print("🔧 Please check your configuration and try again")
        sys.exit(1)