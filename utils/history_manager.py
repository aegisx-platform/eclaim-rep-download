"""History Manager - Manage download_history.json safely"""

import json
import shutil
from pathlib import Path
from datetime import datetime
import humanize


class HistoryManager:
    def __init__(self, history_file='download_history.json'):
        self.history_file = Path(history_file)

    def load_history(self):
        """Load download history from JSON file"""
        if not self.history_file.exists():
            return {'last_run': None, 'downloads': []}

        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading history: {e}")
            return {'last_run': None, 'downloads': []}

    def save_history(self, data):
        """Save history with atomic write (backup first)"""
        # Create backup if file exists
        if self.history_file.exists():
            backup_file = self.history_file.with_suffix('.json.backup')
            shutil.copy2(self.history_file, backup_file)

        # Write to temp file first
        temp_file = self.history_file.with_suffix('.json.tmp')
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            # Atomic rename
            temp_file.replace(self.history_file)
        except Exception as e:
            print(f"Error saving history: {e}")
            if temp_file.exists():
                temp_file.unlink()
            raise

    def get_all_downloads(self):
        """Get all download records"""
        history = self.load_history()
        return history.get('downloads', [])

    def get_download(self, filename):
        """Get single download record by filename"""
        downloads = self.get_all_downloads()
        for download in downloads:
            if download['filename'] == filename:
                return download
        return None

    def delete_download(self, filename):
        """Remove download record from history"""
        history = self.load_history()
        downloads = history.get('downloads', [])

        # Filter out the filename
        history['downloads'] = [d for d in downloads if d['filename'] != filename]

        self.save_history(history)
        return True

    def get_statistics(self):
        """Calculate dashboard statistics"""
        history = self.load_history()
        downloads = history.get('downloads', [])

        total_files = len(downloads)
        total_size = sum(d.get('file_size', 0) for d in downloads)
        last_run = history.get('last_run')

        # Format last run time
        if last_run:
            try:
                last_run_dt = datetime.fromisoformat(last_run)
                last_run_formatted = humanize.naturaltime(last_run_dt)
            except (ValueError, TypeError):
                last_run_formatted = last_run
        else:
            last_run_formatted = 'Never'

        # Get file type breakdown
        file_types = {}
        for download in downloads:
            filename = download['filename']
            # Extract type from filename (e.g., eclaim_10670_OP_... -> OP)
            parts = filename.split('_')
            if len(parts) >= 3:
                file_type = parts[2]  # OP, ORF, IP
                file_types[file_type] = file_types.get(file_type, 0) + 1

        return {
            'total_files': total_files,
            'total_size': humanize.naturalsize(total_size),
            'total_size_bytes': total_size,
            'last_run': last_run_formatted,
            'last_run_raw': last_run,
            'file_types': file_types
        }

    def get_latest(self, n=5):
        """Get n latest downloads"""
        downloads = self.get_all_downloads()

        # Sort by download_date (most recent first)
        sorted_downloads = sorted(
            downloads,
            key=lambda d: d.get('download_date', ''),
            reverse=True
        )

        return sorted_downloads[:n]

    def get_date_range_statistics(self):
        """
        Get statistics grouped by month/year

        Returns:
            dict: Statistics organized by year and month
                {
                  "2568": {
                    "1": {"files": 15, "size": 1234567},
                    "12": {"files": 23, "size": 987654}
                  }
                }
        """
        downloads = self.get_all_downloads()
        stats = {}

        for download in downloads:
            # Get month and year from record (if available)
            month = download.get('month')
            year = download.get('year')

            # If month/year not in record, try to extract from filename or skip
            if not month or not year:
                continue

            # Ensure year key exists
            year_str = str(year)
            if year_str not in stats:
                stats[year_str] = {}

            # Ensure month key exists
            month_str = str(month)
            if month_str not in stats[year_str]:
                stats[year_str][month_str] = {
                    'files': 0,
                    'size': 0
                }

            # Add to statistics
            stats[year_str][month_str]['files'] += 1
            stats[year_str][month_str]['size'] += download.get('file_size', 0)

        # Format sizes
        for year in stats:
            for month in stats[year]:
                stats[year][month]['size_formatted'] = humanize.naturalsize(stats[year][month]['size'])

        return stats

    def get_downloads_by_date(self, month, year):
        """
        Get all downloads for specific month/year

        Args:
            month (int): Month (1-12)
            year (int): Year in Buddhist Era

        Returns:
            list: List of download records for the specified month/year
        """
        downloads = self.get_all_downloads()

        # Filter by month and year
        filtered = [
            d for d in downloads
            if d.get('month') == month and d.get('year') == year
        ]

        # Sort by download date
        filtered.sort(key=lambda d: d.get('download_date', ''), reverse=True)

        return filtered

    def get_available_dates(self):
        """
        Get list of available month/year combinations from downloads

        Returns:
            list: List of dicts with month, year, and count
                [{'month': 1, 'year': 2569, 'count': 54, 'label': 'January 2569'}, ...]
        """
        downloads = self.get_all_downloads()
        date_counts = {}

        month_names = {
            1: 'January', 2: 'February', 3: 'March', 4: 'April',
            5: 'May', 6: 'June', 7: 'July', 8: 'August',
            9: 'September', 10: 'October', 11: 'November', 12: 'December'
        }

        for download in downloads:
            month = download.get('month')
            year = download.get('year')

            # Try to extract from filename if not in metadata
            if month is None or year is None:
                import re
                match = re.search(r'_(\d{4})(\d{2})\d{2}_', download.get('filename', ''))
                if match:
                    year = int(match.group(1))
                    month = int(match.group(2))

            if month and year:
                key = (year, month)
                date_counts[key] = date_counts.get(key, 0) + 1

        # Convert to list and sort (most recent first)
        available_dates = [
            {
                'month': month,
                'year': year,
                'count': count,
                'label': f"{month_names.get(month, month)} {year}"
            }
            for (year, month), count in date_counts.items()
        ]

        # Sort by year and month (descending)
        available_dates.sort(key=lambda d: (d['year'], d['month']), reverse=True)

        return available_dates
