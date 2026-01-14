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

# Job history tracking (optional - may not be available in all environments)
job_history_manager = None
try:
    from utils.job_history_manager import job_history_manager
except ImportError:
    pass  # Running standalone without job tracking

# Direct log writing for real-time logs (works in subprocess)
import json as json_module
REALTIME_LOG_FILE = Path('logs/realtime.log')


def stream_log(message: str, level: str = 'info'):
    """Write log to both console and real-time stream file"""
    print(message, flush=True)
    try:
        REALTIME_LOG_FILE.parent.mkdir(exist_ok=True)
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'source': 'download',
            'message': message
        }
        with open(REALTIME_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json_module.dumps(log_entry) + '\n')
    except Exception:
        pass  # Silently ignore log errors

class EClaimDownloader:
    def __init__(self, month=None, year=None, scheme='ucs', import_each=False, use_db_history=True):
        """
        Initialize E-Claim Downloader

        Args:
            month (int, optional): Month (1-12). Defaults to current month.
            year (int, optional): Year in Buddhist Era. Defaults to current year + 543.
            scheme (str, optional): Insurance scheme code. Defaults to 'ucs'.
                Valid schemes: ucs, ofc, sss, lgo, nhs, bkk, bmt, srt
            import_each (bool, optional): Import each file immediately after download. Defaults to False.
            use_db_history (bool, optional): Use database for history tracking. Defaults to True.
        """
        # Load credentials from settings file first, fallback to env vars
        self.username, self.password = self._load_credentials()
        self.download_dir = Path(os.getenv('DOWNLOAD_DIR', './downloads')) / 'rep'
        self.tracking_file = Path('download_history.json')
        self.iteration_progress_file = Path('download_iteration_progress.json')
        self.import_each = import_each
        self.scheme = scheme
        self.use_db_history = use_db_history
        self._history_db = None

        # Set month and year (default to current date in Buddhist Era)
        now = datetime.now()
        self.month = month if month is not None else now.month
        self.year = year if year is not None else (now.year + 543)  # Convert to Buddhist Era

        # URLs
        self.base_url = 'https://eclaim.nhso.go.th'
        self.login_url = f'{self.base_url}/webComponent/login/LoginAction.do'
        self.validation_url = (
            f'{self.base_url}/webComponent/validation/ValidationMainAction.do?'
            f'mo={self.month}&ye={self.year}&maininscl={self.scheme}'
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
        self.download_dir.mkdir(parents=True, exist_ok=True)

        # Load download history
        self.download_history = self._load_history()

    def _update_iteration_progress(self, current_idx: int, total_files: int, current_file: str = None):
        """
        Update download iteration progress for real-time tracking

        Args:
            current_idx: Current file index (1-based)
            total_files: Total number of files to download
            current_file: Name of current file being downloaded
        """
        try:
            progress = {
                'month': self.month,
                'year': self.year,
                'scheme': self.scheme,
                'current_idx': current_idx,
                'total_files': total_files,
                'current_file': current_file,
                'updated_at': datetime.now().isoformat()
            }
            with open(self.iteration_progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress, f, ensure_ascii=False, indent=2)
        except Exception:
            pass  # Silently ignore progress update errors

    def _load_credentials(self):
        """
        Load credentials from settings file (with random selection) or environment variables

        Returns:
            (username, password) tuple
        """
        # Try to use settings manager for random credential selection
        try:
            from utils.settings_manager import SettingsManager
            settings_manager = SettingsManager()
            username, password = settings_manager.get_eclaim_credentials(random_select=True)
            if username and password:
                stream_log(f"Using credential: {username[:4]}***{username[-4:]}", 'info')
                return username, password
        except Exception as e:
            stream_log(f"Settings manager not available: {e}", 'warning')

        # Fallback to direct settings file read
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

    def _get_history_db(self):
        """Get database history manager instance"""
        if not self.use_db_history:
            return None

        if self._history_db is None:
            try:
                from utils.download_history_db import DownloadHistoryDB
                self._history_db = DownloadHistoryDB()
                self._history_db.connect()
            except Exception as e:
                stream_log(f"Warning: Could not connect to history DB: {e}", 'warning')
                return None

        return self._history_db

    def _is_already_downloaded(self, filename):
        """
        Check if file was already downloaded

        Note: Filename-based deduplication works because each scheme has
        different files with unique filenames (includes timestamp).
        We also check scheme for extra safety.

        First checks database (if enabled), then falls back to JSON history.
        Failed downloads are NOT counted as downloaded (can be retried).
        """
        # Try database first if enabled
        if self.use_db_history:
            db = self._get_history_db()
            if db:
                try:
                    # Only check successful downloads (failed can be retried)
                    return db.is_downloaded('rep', filename, check_file_exists=True)
                except Exception as e:
                    stream_log(f"Warning: DB check failed, falling back to JSON: {e}", 'warning')

        # Fallback to JSON history
        for d in self.download_history['downloads']:
            if d['filename'] == filename:
                # For legacy records without scheme, assume 'ucs'
                record_scheme = d.get('scheme', 'ucs')
                if record_scheme == self.scheme:
                    # Also check if file exists
                    file_path = d.get('file_path')
                    if file_path and Path(file_path).exists():
                        return True
        return False

    def _import_file(self, file_path, filename):
        """
        Import single file to database immediately after download

        Args:
            file_path (str): Path to downloaded file
            filename (str): Filename
        """
        try:
            stream_log(f"    ⚡ Importing {filename} to database...")

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
                stream_log(f"    ✓ Imported: {imported}/{total} records", 'success')
            else:
                error = result.get('error', 'Unknown error')
                stream_log(f"    ✗ Import failed: {error}", 'error')

        except Exception as e:
            stream_log(f"    ✗ Import error: {str(e)}", 'error')

    def login(self):
        """Login to e-claim system"""
        stream_log(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Logging in...")

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

            stream_log(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Login successful!", 'success')
            return True

        except Exception as e:
            stream_log(f"✗ Login error: {str(e)}", 'error')
            raise

    def get_download_links(self):
        """Get all download Excel links from validation page"""
        stream_log(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Fetching validation page...")

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

            stream_log(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Found {len(unique_links)} unique download links")
            return unique_links

        except Exception as e:
            stream_log(f"✗ Error fetching download links: {str(e)}", 'error')
            raise

    def download_files(self, download_links):
        """Download Excel files"""
        downloaded_count = 0
        skipped_count = 0
        error_count = 0

        total_files = len(download_links)

        for idx, link_info in enumerate(download_links, 1):
            filename = link_info['filename']
            url = link_info['url']

            # Update iteration progress for real-time tracking
            self._update_iteration_progress(idx, total_files, filename)

            # Check if already downloaded
            if self._is_already_downloaded(filename):
                stream_log(f"[{idx}/{total_files}] Skipping {filename} (already downloaded)")
                skipped_count += 1
                continue

            # Retry logic
            max_retries = 2
            retry_count = 0
            success = False

            while retry_count <= max_retries and not success:
                try:
                    if retry_count > 0:
                        stream_log(f"[{idx}/{total_files}] Retry {retry_count}/{max_retries} for {filename}...", 'warning')
                        time.sleep(2)  # Wait before retry
                    else:
                        stream_log(f"[{idx}/{total_files}] Downloading {filename}...")

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

                    # Record download to JSON history
                    download_record = {
                        'filename': filename,
                        'download_date': datetime.now().isoformat(),
                        'file_path': str(file_path),
                        'file_size': file_size,
                        'url': url,
                        'month': self.month,
                        'year': self.year,
                        'scheme': self.scheme
                    }
                    self.download_history['downloads'].append(download_record)

                    # Record to database if enabled
                    if self.use_db_history:
                        try:
                            db = self._get_history_db()
                            if db:
                                db_record = {
                                    'filename': filename,
                                    'scheme': self.scheme,
                                    'fiscal_year': self.year,
                                    'service_month': self.month,
                                    'file_size': file_size,
                                    'file_path': str(file_path),
                                    'source_url': url,
                                }
                                db.record_download('rep', db_record, status='success')
                        except Exception as db_error:
                            stream_log(f"    Warning: Could not save to DB: {db_error}", 'warning')

                    downloaded_count += 1
                    stream_log(f"[{idx}/{total_files}] ✓ Downloaded: {filename} ({file_size:,} bytes)", 'success')
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
                    last_error = str(e)
                    if retry_count > max_retries:
                        stream_log(f"[{idx}/{total_files}] ✗ Failed after {max_retries} retries: {filename}", 'error')
                        stream_log(f"    Error: {last_error}", 'error')

                        # Record failed download to database for later retry
                        if self.use_db_history:
                            try:
                                db = self._get_history_db()
                                if db:
                                    failed_record = {
                                        'filename': filename,
                                        'scheme': self.scheme,
                                        'fiscal_year': self.year,
                                        'service_month': self.month,
                                        'source_url': url,
                                    }
                                    db.record_failed_download('rep', failed_record, last_error)
                                    stream_log(f"    📝 Recorded for retry later", 'info')
                            except Exception as db_error:
                                stream_log(f"    Warning: Could not record failure: {db_error}", 'warning')

                        error_count += 1
                    continue

        return downloaded_count, skipped_count, error_count

    def run(self):
        """Main execution"""
        stream_log("="*60)
        stream_log("E-Claim Excel File Downloader (HTTP Client)")
        stream_log("="*60)
        stream_log(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        stream_log(f"Month/Year: {self.month}/{self.year} BE")
        stream_log(f"Insurance Scheme: {self.scheme.upper()}")

        try:
            # Login
            self.login()

            # Get download links
            download_links = self.get_download_links()

            if not download_links:
                stream_log("No download links found!", 'warning')
                return

            # Download files
            downloaded, skipped, errors = self.download_files(download_links)

            # Update last run time
            self.download_history['last_run'] = datetime.now().isoformat()

            # Save history
            self._save_history()

            # Summary
            stream_log("="*60)
            stream_log("Download Summary", 'success')
            stream_log("="*60)
            stream_log(f"Total files found: {len(download_links)}")
            stream_log(f"✓ Downloaded: {downloaded}", 'success')
            stream_log(f"⊘ Skipped (already downloaded): {skipped}")
            stream_log(f"✗ Errors: {errors}", 'error' if errors > 0 else 'info')
            stream_log(f"Download directory: {self.download_dir.absolute()}")
            stream_log(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 'success')
            stream_log("="*60)

        except Exception as e:
            stream_log(f"✗ Error: {str(e)}", 'error')
            import traceback
            traceback.print_exc()
            raise

def main():
    """Entry point"""
    import argparse

    # Valid scheme codes
    VALID_SCHEMES = ['ucs', 'ofc', 'sss', 'lgo', 'nhs', 'bkk', 'bmt', 'srt']

    parser = argparse.ArgumentParser(
        description='E-Claim Excel File Downloader',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download current month (default scheme: UCS)
  python eclaim_downloader_http.py

  # Download specific month and year (Buddhist Era)
  python eclaim_downloader_http.py --month 12 --year 2568

  # Download from different insurance scheme
  python eclaim_downloader_http.py --scheme ofc

  # Download SSS scheme for January 2025
  python eclaim_downloader_http.py --month 1 --year 2568 --scheme sss

Insurance Schemes:
  ucs  - Universal Coverage Scheme (บัตรทอง)
  ofc  - Government Officer (ข้าราชการ)
  sss  - Social Security Scheme (ประกันสังคม)
  lgo  - Local Government Organization (อปท.)
  nhs  - NHSO Staff (สปสช.)
  bkk  - Bangkok Metropolitan Staff (กทม.)
  bmt  - BMTA Staff (ขสมก.)
  srt  - State Railway of Thailand Staff (รฟท.)
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
        '--scheme',
        type=str,
        choices=VALID_SCHEMES,
        default='ucs',
        help='Insurance scheme code. Defaults to "ucs" (Universal Coverage Scheme).'
    )

    parser.add_argument(
        '--import-each',
        action='store_true',
        help='Import each file to database immediately after download (concurrent mode)'
    )

    args = parser.parse_args()

    # Create downloader with specified month/year/scheme (or defaults)
    downloader = EClaimDownloader(
        month=args.month,
        year=args.year,
        scheme=args.scheme,
        import_each=args.import_each
    )
    downloader.run()

if __name__ == '__main__':
    main()
