#!/usr/bin/env python3
"""
E-Claim Excel File Downloader (HTTP Client Version)
Automatically downloads Excel files from NHSO e-claim validation page using HTTP requests
"""

import os
import json
import time
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class EClaimDownloader:
    def __init__(self, month=None, year=None, import_each=False):
        """
        Initialize E-Claim Downloader

        Args:
            month (int, optional): Month (1-12). Defaults to current month.
            year (int, optional): Year in Buddhist Era. Defaults to current year + 543.
            import_each (bool, optional): Import each file immediately after download. Defaults to False.
        """
        # Load credentials from settings file first, fallback to env vars
        self.username, self.password = self._load_credentials()
        self.download_dir = Path(os.getenv('DOWNLOAD_DIR', './downloads'))
        self.tracking_file = Path('download_history.json')
        self.import_each = import_each

        # Set month and year (default to current date in Buddhist Era)
        now = datetime.now()
        self.month = month if month is not None else now.month
        self.year = year if year is not None else (now.year + 543)  # Convert to Buddhist Era

        # URLs
        self.base_url = 'https://eclaim.nhso.go.th'
        self.login_url = f'{self.base_url}/webComponent/login/LoginAction.do'
        self.validation_url = (
            f'{self.base_url}/webComponent/validation/ValidationMainAction.do?'
            f'mo={self.month}&ye={self.year}&maininscl=ucs'
        )

        # Create session with cookies
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'th,en-US;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })

        # Create download directory
        self.download_dir.mkdir(exist_ok=True)

        # Load download history
        self.download_history = self._load_history()

    def _load_credentials(self):
        """
        Load credentials from settings file or environment variables

        Returns:
            (username, password) tuple
        """
        # Try to load from settings file first
        settings_file = Path('config/settings.json')
        if settings_file.exists():
            try:
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    username = settings.get('eclaim_username', '').strip()
                    password = settings.get('eclaim_password', '').strip()
                    if username and password:
                        return username, password
            except Exception:
                pass

        # Fallback to environment variables
        username = os.getenv('ECLAIM_USERNAME', '').strip()
        password = os.getenv('ECLAIM_PASSWORD', '').strip()

        if not username or not password:
            raise ValueError(
                "E-Claim credentials not configured!\n"
                "Please configure credentials via:\n"
                "1. Web UI Settings page (http://localhost:5001/settings), or\n"
                "2. Environment variables: ECLAIM_USERNAME and ECLAIM_PASSWORD"
            )

        return username, password

    def _load_history(self):
        """Load download history from JSON file"""
        if self.tracking_file.exists():
            with open(self.tracking_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            'last_run': None,
            'downloads': []
        }

    def _save_history(self):
        """Save download history to JSON file"""
        with open(self.tracking_file, 'w', encoding='utf-8') as f:
            json.dump(self.download_history, f, ensure_ascii=False, indent=2)

    def _is_already_downloaded(self, filename):
        """Check if file was already downloaded"""
        return any(d['filename'] == filename for d in self.download_history['downloads'])

    def _import_file(self, file_path, filename):
        """
        Import single file to database immediately after download

        Args:
            file_path (str): Path to downloaded file
            filename (str): Filename
        """
        try:
            print(f"    ⚡ Importing {filename} to database...")

            # Import from eclaim_import module (V2 with Schema V2)
            from utils.eclaim.importer_v2 import import_eclaim_file
            from config.database import get_db_config

            # Get database config
            db_config = get_db_config()

            # Import file
            result = import_eclaim_file(file_path, db_config)

            if result['success']:
                imported = result.get('imported_records', 0)
                total = result.get('total_records', 0)
                print(f"    ✓ Imported: {imported}/{total} records")
            else:
                error = result.get('error', 'Unknown error')
                print(f"    ✗ Import failed: {error}")

        except Exception as e:
            print(f"    ✗ Import error: {str(e)}")

    def login(self):
        """Login to e-claim system"""
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Logging in...")

        try:
            # First, get the login page to establish session
            response = self.session.get(self.login_url, timeout=120)
            response.raise_for_status()

            # Prepare login data
            login_data = {
                'user': self.username,
                'pass': self.password
            }

            # Post login form
            response = self.session.post(
                self.login_url,
                data=login_data,
                timeout=120,
                allow_redirects=True
            )
            response.raise_for_status()

            # Check if login successful (you might need to adjust this check)
            if 'login' in response.url.lower() and 'error' in response.text.lower():
                raise Exception("Login failed - invalid credentials or error page")

            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Login successful!")
            return True

        except Exception as e:
            print(f"✗ Login error: {str(e)}")
            raise

    def get_download_links(self):
        """Get all download Excel links from validation page"""
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Fetching validation page...")

        try:
            response = self.session.get(self.validation_url, timeout=120)
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.content, 'lxml')

            # Find all download excel links
            download_links = []

            # Find all tables
            tables = soup.find_all('table')

            for table in tables:
                rows = table.find_all('tr')

                for row in rows:
                    # Look for download excel link
                    excel_links = row.find_all('a', string=re.compile(r'download excel', re.IGNORECASE))

                    for excel_link in excel_links:
                        excel_href = excel_link.get('href')

                        if excel_href:
                            # Extract filename from URL parameter 'fn'
                            parsed = urlparse(excel_href)
                            params = parse_qs(parsed.query)

                            filename = None
                            if 'fn' in params:
                                filename = params['fn'][0]
                            elif 'filename' in params:
                                # Extract filename from 'filename' parameter and replace .ecd with .xls
                                filename = params['filename'][0].replace('.ecd', '.xls')
                            elif 'file' in params:
                                filename = params['file'][0]

                            # If still no filename, try rep link
                            if not filename:
                                rep_links = row.find_all('a', string=re.compile(r'rep_eclaim', re.IGNORECASE))
                                if rep_links:
                                    rep_href = rep_links[0].get('href')
                                    if rep_href:
                                        filename = rep_href.split('/')[-1].replace('.ecd', '.xls')

                            # Last resort - generate filename
                            if not filename:
                                filename = f"eclaim_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xls"

                            # Build full URL
                            full_url = urljoin(self.base_url, excel_href)

                            download_links.append({
                                'url': full_url,
                                'filename': filename
                            })

            # Remove duplicates
            unique_links = []
            seen_filenames = set()

            for link in download_links:
                if link['filename'] not in seen_filenames:
                    unique_links.append(link)
                    seen_filenames.add(link['filename'])

            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Found {len(unique_links)} unique download links")
            return unique_links

        except Exception as e:
            print(f"✗ Error fetching download links: {str(e)}")
            raise

    def download_files(self, download_links):
        """Download Excel files"""
        downloaded_count = 0
        skipped_count = 0
        error_count = 0

        for idx, link_info in enumerate(download_links, 1):
            filename = link_info['filename']
            url = link_info['url']

            # Check if already downloaded
            if self._is_already_downloaded(filename):
                print(f"[{idx}/{len(download_links)}] Skipping {filename} (already downloaded)")
                skipped_count += 1
                continue

            # Retry logic
            max_retries = 2
            retry_count = 0
            success = False

            while retry_count <= max_retries and not success:
                try:
                    if retry_count > 0:
                        print(f"[{idx}/{len(download_links)}] Retry {retry_count}/{max_retries} for {filename}...")
                        time.sleep(2)  # Wait before retry
                    else:
                        print(f"[{idx}/{len(download_links)}] Downloading {filename}...")

                    # Download file with increased timeout
                    response = self.session.get(url, timeout=120, stream=True)
                    response.raise_for_status()

                    # Save file
                    file_path = self.download_dir / filename

                    with open(file_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)

                    # Get file size
                    file_size = file_path.stat().st_size

                    # Check if file is valid (not empty or too small)
                    if file_size < 100:
                        raise Exception(f"Downloaded file too small ({file_size} bytes)")

                    # Record download
                    self.download_history['downloads'].append({
                        'filename': filename,
                        'download_date': datetime.now().isoformat(),
                        'file_path': str(file_path),
                        'file_size': file_size,
                        'url': url,
                        'month': self.month,
                        'year': self.year
                    })

                    downloaded_count += 1
                    print(f"[{idx}/{len(download_links)}] ✓ Downloaded: {filename} ({file_size:,} bytes)")
                    success = True

                    # Save history after each download for real-time tracking
                    self._save_history()

                    # Import immediately if flag is set
                    if self.import_each:
                        self._import_file(str(file_path), filename)

                    # Delay to avoid overwhelming server
                    time.sleep(1)

                except Exception as e:
                    retry_count += 1
                    if retry_count > max_retries:
                        print(f"[{idx}/{len(download_links)}] ✗ Failed after {max_retries} retries: {filename}")
                        print(f"    Error: {str(e)}")
                        error_count += 1
                    continue

        return downloaded_count, skipped_count, error_count

    def run(self):
        """Main execution"""
        print("="*60)
        print("E-Claim Excel File Downloader (HTTP Client)")
        print("="*60)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        try:
            # Login
            self.login()

            # Get download links
            download_links = self.get_download_links()

            if not download_links:
                print("No download links found!")
                return

            # Download files
            downloaded, skipped, errors = self.download_files(download_links)

            # Update last run time
            self.download_history['last_run'] = datetime.now().isoformat()

            # Save history
            self._save_history()

            # Summary
            print()
            print("="*60)
            print("Download Summary")
            print("="*60)
            print(f"Total files found: {len(download_links)}")
            print(f"✓ Downloaded: {downloaded}")
            print(f"⊘ Skipped (already downloaded): {skipped}")
            print(f"✗ Errors: {errors}")
            print(f"Total downloads in history: {len(self.download_history['downloads'])}")
            print(f"Download directory: {self.download_dir.absolute()}")
            print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*60)

        except Exception as e:
            print(f"\n✗ Error: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

def main():
    """Entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='E-Claim Excel File Downloader',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download current month (default)
  python eclaim_downloader_http.py

  # Download specific month and year (Buddhist Era)
  python eclaim_downloader_http.py --month 12 --year 2568

  # Download January 2025 (2568 BE)
  python eclaim_downloader_http.py --month 1 --year 2568
        """
    )

    parser.add_argument(
        '--month',
        type=int,
        choices=range(1, 13),
        help='Month to download (1-12). Defaults to current month.'
    )

    parser.add_argument(
        '--year',
        type=int,
        help='Year in Buddhist Era (BE = Gregorian + 543). Defaults to current year.'
    )

    parser.add_argument(
        '--import-each',
        action='store_true',
        help='Import each file to database immediately after download (concurrent mode)'
    )

    args = parser.parse_args()

    # Create downloader with specified month/year (or defaults)
    downloader = EClaimDownloader(
        month=args.month,
        year=args.year,
        import_each=args.import_each
    )
    downloader.run()

if __name__ == '__main__':
    main()
