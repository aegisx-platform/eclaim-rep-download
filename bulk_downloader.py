#!/usr/bin/env python3
"""
Bulk Downloader - Orchestrate sequential downloads across multiple months/years
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
import subprocess

# Import the main downloader
from eclaim_downloader_http import EClaimDownloader


class BulkDownloader:
    def __init__(self):
        self.progress_file = Path('bulk_download_progress.json')
        self.delay_between_months = 10  # seconds between each month download

    def generate_date_range(self, start_month, start_year, end_month, end_year):
        """
        Generate list of (month, year) tuples for the date range

        Args:
            start_month (int): Starting month (1-12)
            start_year (int): Starting year in Buddhist Era
            end_month (int): Ending month (1-12)
            end_year (int): Ending year in Buddhist Era

        Returns:
            list: List of (month, year) tuples

        Example:
            generate_date_range(1, 2568, 3, 2568) -> [(1,2568), (2,2568), (3,2568)]
            generate_date_range(11, 2567, 2, 2568) -> [(11,2567), (12,2567), (1,2568), (2,2568)]
        """
        date_range = []
        current_month = start_month
        current_year = start_year

        while True:
            date_range.append((current_month, current_year))

            # Check if we've reached the end
            if current_month == end_month and current_year == end_year:
                break

            # Move to next month
            current_month += 1
            if current_month > 12:
                current_month = 1
                current_year += 1

            # Safety check to prevent infinite loop
            if current_year > end_year + 1:
                break

        return date_range

    def load_progress(self):
        """Load progress from file"""
        if self.progress_file.exists():
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def save_progress(self, progress):
        """Save progress to file"""
        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)

    def run_bulk_download(self, start_month, start_year, end_month, end_year):
        """
        Execute downloads sequentially for each month in the date range

        Args:
            start_month (int): Starting month (1-12)
            start_year (int): Starting year in BE
            end_month (int): Ending month (1-12)
            end_year (int): Ending year in BE
        """
        # Generate date range
        date_range = self.generate_date_range(start_month, start_year, end_month, end_year)

        # Initialize progress tracking
        bulk_id = f"bulk_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
        progress = {
            'bulk_id': bulk_id,
            'start_date': {'month': start_month, 'year': start_year},
            'end_date': {'month': end_month, 'year': end_year},
            'total_months': len(date_range),
            'completed_months': 0,
            'current_month': None,
            'status': 'running',
            'started_at': datetime.now().isoformat(),
            'monthly_results': []
        }

        self.save_progress(progress)

        print("="*60)
        print("Bulk Download Started")
        print("="*60)
        print(f"Date range: {start_month}/{start_year} to {end_month}/{end_year}")
        print(f"Total months: {len(date_range)}")
        print(f"Bulk ID: {bulk_id}")
        print("="*60)
        print()

        # Process each month
        for idx, (month, year) in enumerate(date_range, 1):
            print(f"\n[{idx}/{len(date_range)}] Processing month {month}/{year}...")
            print("-"*60)

            # Update current month in progress
            progress['current_month'] = {'month': month, 'year': year}
            self.save_progress(progress)

            monthly_result = {
                'month': month,
                'year': year,
                'status': 'running',
                'files': 0,
                'started_at': datetime.now().isoformat()
            }

            try:
                # Create downloader for this specific month/year
                downloader = EClaimDownloader(month=month, year=year)

                # Run the download
                downloader.run()

                # Mark as completed
                monthly_result['status'] = 'completed'
                monthly_result['completed_at'] = datetime.now().isoformat()

                # Count files for this month (approximate - could enhance later)
                # For now, we'll mark it as completed without counting
                print(f"✓ Month {month}/{year} completed successfully")

            except Exception as e:
                # Handle error but continue with next month
                print(f"✗ Error processing month {month}/{year}: {str(e)}")
                monthly_result['status'] = 'failed'
                monthly_result['error'] = str(e)
                monthly_result['completed_at'] = datetime.now().isoformat()

            # Record monthly result
            progress['monthly_results'].append(monthly_result)
            progress['completed_months'] = idx
            self.save_progress(progress)

            # Delay before next month (except for the last one)
            if idx < len(date_range):
                print(f"\nWaiting {self.delay_between_months} seconds before next month...")
                time.sleep(self.delay_between_months)

        # Mark bulk operation as completed
        progress['status'] = 'completed'
        progress['completed_at'] = datetime.now().isoformat()
        self.save_progress(progress)

        # Summary
        print("\n" + "="*60)
        print("Bulk Download Summary")
        print("="*60)
        print(f"Total months processed: {len(date_range)}")
        print(f"Completed: {progress['completed_months']}")
        print(f"Failed: {sum(1 for r in progress['monthly_results'] if r['status'] == 'failed')}")
        print(f"Started at: {progress['started_at']}")
        print(f"Completed at: {progress['completed_at']}")
        print("="*60)


def main():
    """Entry point for bulk downloader"""
    if len(sys.argv) != 3:
        print("Usage: python bulk_downloader.py START END")
        print("  START: start_month,start_year (e.g., 1,2568)")
        print("  END: end_month,end_year (e.g., 12,2568)")
        print()
        print("Example:")
        print("  python bulk_downloader.py 1,2568 12,2568")
        sys.exit(1)

    try:
        # Parse arguments
        start_parts = sys.argv[1].split(',')
        end_parts = sys.argv[2].split(',')

        start_month = int(start_parts[0])
        start_year = int(start_parts[1])
        end_month = int(end_parts[0])
        end_year = int(end_parts[1])

        # Validate
        if not (1 <= start_month <= 12 and 1 <= end_month <= 12):
            print("Error: Month must be between 1 and 12")
            sys.exit(1)

        if start_year > end_year or (start_year == end_year and start_month > end_month):
            print("Error: Start date must be before or equal to end date")
            sys.exit(1)

        # Run bulk download
        bulk_downloader = BulkDownloader()
        bulk_downloader.run_bulk_download(start_month, start_year, end_month, end_year)

    except Exception as e:
        print(f"\n✗ Bulk download error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
