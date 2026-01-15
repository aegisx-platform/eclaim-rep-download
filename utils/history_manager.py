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

    def add_download(self, download_record):
        """
        Add a download record to history

        Args:
            download_record (dict): Download record with fields:
                - filename (required)
                - file_size (optional)
                - download_date (optional)
                - month, year (optional)
                - scheme (optional)

        Returns:
            bool: True if added, False if already exists
        """
        history = self.load_history()
        downloads = history.get('downloads', [])

        # Check if already exists
        filename = download_record.get('filename')
        if any(d['filename'] == filename for d in downloads):
            return False

        # Add to downloads
        downloads.append(download_record)
        history['downloads'] = downloads

        self.save_history(history)
        return True

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

    def get_downloads_by_scheme(self, scheme):
        """
        Get all downloads for a specific insurance scheme

        Args:
            scheme (str): Scheme code (e.g., 'ucs', 'ofc')

        Returns:
            list: List of download records for the specified scheme
        """
        downloads = self.get_all_downloads()

        # Filter by scheme (default to 'ucs' for legacy records)
        filtered = [
            d for d in downloads
            if d.get('scheme', 'ucs') == scheme
        ]

        # Sort by download date (most recent first)
        filtered.sort(key=lambda d: d.get('download_date', ''), reverse=True)

        return filtered

    def get_statistics_by_scheme(self):
        """
        Get statistics grouped by insurance scheme

        Returns:
            dict: Statistics organized by scheme
                {
                  "ucs": {"files": 54, "size": 12345678, "size_formatted": "12.3 MB"},
                  "ofc": {"files": 23, "size": 9876543, "size_formatted": "9.9 MB"}
                }
        """
        downloads = self.get_all_downloads()
        stats = {}

        for download in downloads:
            # Get scheme from record (default to 'ucs' for legacy)
            scheme = download.get('scheme', 'ucs')

            if scheme not in stats:
                stats[scheme] = {
                    'files': 0,
                    'size': 0
                }

            stats[scheme]['files'] += 1
            stats[scheme]['size'] += download.get('file_size', 0)

        # Format sizes
        for scheme in stats:
            stats[scheme]['size_formatted'] = humanize.naturalsize(stats[scheme]['size'])

        return stats

    def get_available_schemes(self):
        """
        Get list of schemes that have downloaded files

        Returns:
            list: List of dicts with scheme info and counts
                [{'scheme': 'ucs', 'count': 54, 'size': 12345678}, ...]
        """
        stats = self.get_statistics_by_scheme()

        # Scheme display names
        scheme_names = {
            'ucs': 'สิทธิบัตรทอง (UCS)',
            'ofc': 'สิทธิข้าราชการ (OFC)',
            'sss': 'สิทธิประกันสังคม (SSS)',
            'lgo': 'สิทธิ อปท. (LGO)',
            'nhs': 'สิทธิ สปสช. (NHS)',
            'bkk': 'สิทธิ กทม. (BKK)',
            'bmt': 'สิทธิ ขสมก. (BMT)',
            'srt': 'สิทธิ รฟท. (SRT)'
        }

        # Convert to list
        available_schemes = [
            {
                'scheme': scheme,
                'name': scheme_names.get(scheme, scheme.upper()),
                'count': data['files'],
                'size': data['size'],
                'size_formatted': data['size_formatted']
            }
            for scheme, data in stats.items()
        ]

        # Sort by file count (descending)
        available_schemes.sort(key=lambda s: s['count'], reverse=True)

        return available_schemes

    def get_downloads_by_date_and_scheme(self, month, year, scheme=None):
        """
        Get all downloads for specific month/year and optionally scheme

        Args:
            month (int): Month (1-12)
            year (int): Year in Buddhist Era
            scheme (str, optional): Scheme code to filter

        Returns:
            list: List of download records
        """
        downloads = self.get_all_downloads()

        # Filter by month and year
        filtered = [
            d for d in downloads
            if d.get('month') == month and d.get('year') == year
        ]

        # Optionally filter by scheme
        if scheme:
            filtered = [
                d for d in filtered
                if d.get('scheme', 'ucs') == scheme
            ]

        # Sort by download date
        filtered.sort(key=lambda d: d.get('download_date', ''), reverse=True)

        return filtered

    def scan_and_register_files(self, directory='downloads/rep'):
        """
        Scan a directory for .xls files and register them in history.
        Files not in history will be added with metadata extracted from filename.

        Args:
            directory (str): Path to scan for files

        Returns:
            dict: Report with added, skipped, and error counts
        """
        import re
        from pathlib import Path

        report = {
            'added': 0,
            'skipped': 0,
            'errors': 0,
            'error_files': [],
            'directory': directory
        }

        scan_dir = Path(directory)
        if not scan_dir.exists():
            report['errors'] = 1
            report['error_files'].append(f'Directory not found: {directory}')
            return report

        # Get all .xls files
        xls_files = list(scan_dir.glob('*.xls'))

        for file_path in xls_files:
            try:
                filename = file_path.name

                # Check if already in history
                if self.get_download(filename) is not None:
                    report['skipped'] += 1
                    continue

                # Extract metadata from filename
                # Format: eclaim_10670_OP_25681001_123456789.xls
                # Or: STM_10670_IPUCS256810_01.xls
                month = None
                year = None
                file_type = None
                scheme = 'ucs'

                # Try eclaim format: eclaim_10670_OP_25681001_xxx.xls
                match = re.search(r'eclaim_\d+_(\w+)_(\d{4})(\d{2})\d{2}_', filename)
                if match:
                    file_type = match.group(1)  # OP, IP, ORF
                    year = int(match.group(2))   # 2568
                    month = int(match.group(3))  # 10

                    # Detect scheme from filename if present
                    scheme_match = re.search(r'_(ucs|ofc|sss|lgo|nhs|bkk)_', filename.lower())
                    if scheme_match:
                        scheme = scheme_match.group(1)

                # Get file size and modification time
                stat = file_path.stat()
                file_size = stat.st_size
                mtime = datetime.fromtimestamp(stat.st_mtime)

                # Create download record
                download_record = {
                    'filename': filename,
                    'file_size': file_size,
                    'download_date': mtime.isoformat(),
                    'source': 'file_scan',
                }

                if month:
                    download_record['month'] = month
                if year:
                    download_record['year'] = year
                if file_type:
                    download_record['file_type'] = file_type
                if scheme:
                    download_record['scheme'] = scheme

                # Add to history
                if self.add_download(download_record):
                    report['added'] += 1
                else:
                    report['skipped'] += 1

            except Exception as e:
                report['errors'] += 1
                report['error_files'].append(f'{filename}: {str(e)}')

        return report
