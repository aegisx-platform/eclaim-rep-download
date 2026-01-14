"""
Parallel Downloader for E-Claim System

This module provides parallel downloading capabilities using multiple
browser sessions to speed up file downloads from NHSO e-claim system.
"""

import os
import json
import time
import threading
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
from typing import List, Dict, Optional, Callable
from urllib.parse import urljoin, urlparse, parse_qs
import re

import requests
from bs4 import BeautifulSoup

from utils.browser_fingerprints import (
    create_session_pool,
    rotate_session,
    create_session_with_fingerprint,
    get_fingerprint
)
from utils.log_stream import stream_log
from config.db_pool import get_connection, return_connection

# Configuration
PARALLEL_CONFIG = {
    'download': {
        'max_workers': 3,          # 3 parallel downloads (conservative)
        'per_file_delay': 1.0,     # delay after each file download
        'per_session_rate': 3.0,   # seconds between files in same session
        'backoff_base': 5,         # base backoff (seconds)
        'backoff_max': 60,         # max backoff
        'retry_count': 3,          # number of retries
        'timeout': 120,            # request timeout
    },
    'import': {
        'max_workers': 3,          # 3 parallel imports
        'batch_size': 100,         # records per batch
    }
}


class ParallelDownloader:
    """
    Parallel file downloader using multiple browser sessions.

    This class manages a pool of HTTP sessions with different browser
    fingerprints to download files concurrently while avoiding rate limiting.
    Supports multiple NHSO accounts for better distribution.
    """

    def __init__(
        self,
        credentials: List[Dict],  # List of {"username": "", "password": "", "note": ""}
        month: int,
        year: int,
        scheme: str = 'ucs',
        max_workers: int = None,
        download_dir: str = 'downloads/rep',
        progress_callback: Callable = None
    ):
        # Store credentials list (filter enabled only)
        self.credentials = [c for c in credentials if c.get('enabled', True)]
        if not self.credentials:
            raise ValueError("No enabled credentials provided")

        self.month = month
        self.year = year
        self.scheme = scheme
        self.max_workers = max_workers or PARALLEL_CONFIG['download']['max_workers']
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.progress_callback = progress_callback

        # Check if we have multiple accounts
        self.multi_account = len(self.credentials) > 1
        if self.multi_account:
            stream_log(f"Multi-account mode: {len(self.credentials)} accounts available", 'info')

        # URLs (same as regular downloader - webComponent endpoints work, .aspx returns 500)
        self.base_url = "https://eclaim.nhso.go.th"
        self.login_url = f"{self.base_url}/webComponent/login/LoginAction.do"
        self.validation_url = f"{self.base_url}/webComponent/validation/ValidationMainAction.do?mo={month}&ye={year}&maininscl={scheme}"

        # Session pool
        self.session_pool = []
        self.pool_lock = threading.Lock()

        # Progress tracking
        self.progress = {
            'status': 'idle',
            'total': 0,
            'completed': 0,
            'failed': 0,
            'skipped': 0,
            'current_files': {},  # worker_id -> filename
            'workers': [],
            'start_time': None,
            'end_time': None,
            'errors': [],
            'multi_account': self.multi_account,
            'accounts_used': len(self.credentials),
        }
        self.progress_lock = threading.Lock()

        # Progress file
        self.progress_file = Path('parallel_download_progress.json')

        # Download history - now using database (no need to load entire history)
        # Just check DB on demand for each file

    def _is_already_downloaded(self, filename: str) -> bool:
        """Check if file was already downloaded (using database)"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 FROM download_history
                WHERE download_type = 'rep'
                  AND filename = %s
                  AND file_exists = TRUE
                  AND download_status = 'success'
            """, (filename,))
            exists_in_db = cursor.fetchone() is not None
            cursor.close()
            return_connection(conn)
            conn = None

            # Also check if file exists on disk
            if exists_in_db:
                file_path = self.download_dir / filename
                if file_path.exists():
                    return True

            return False
        except Exception as e:
            stream_log(f"Warning: Could not check download history: {e}", 'warning')
            return False
        finally:
            if conn:
                return_connection(conn)

    def _record_download(self, filename: str, file_size: int, url: str):
        """Record a successful download to database (thread-safe)"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            file_path = str(self.download_dir / filename)

            cursor.execute("""
                INSERT INTO download_history
                (download_type, filename, scheme, fiscal_year, service_month,
                 file_size, file_path, source_url, file_exists, download_status)
                VALUES ('rep', %s, %s, %s, %s, %s, %s, %s, TRUE, 'success')
                ON CONFLICT (download_type, filename) DO UPDATE SET
                    file_size = EXCLUDED.file_size,
                    file_path = EXCLUDED.file_path,
                    file_exists = TRUE,
                    download_status = 'success',
                    updated_at = CURRENT_TIMESTAMP
            """, (filename, self.scheme, self.year, self.month,
                  file_size, file_path, url))

            conn.commit()
            cursor.close()
            return_connection(conn)
            conn = None

        except Exception as e:
            stream_log(f"Warning: Could not record download to DB: {e}", 'warning')
            if conn:
                conn.rollback()
        finally:
            if conn:
                return_connection(conn)

    def _save_progress(self):
        """Save progress to file for real-time tracking"""
        try:
            with self.progress_lock:
                progress_data = self.progress.copy()

            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            stream_log(f"Warning: Could not save progress: {e}", 'warning')

    def _update_progress(self, **kwargs):
        """Update progress and save to file"""
        with self.progress_lock:
            for key, value in kwargs.items():
                if key in self.progress:
                    self.progress[key] = value

        self._save_progress()

        if self.progress_callback:
            try:
                self.progress_callback(self.progress)
            except Exception:
                pass

    def initialize_sessions(self) -> bool:
        """
        Create session pool and login each session.
        If multiple accounts available, each worker uses a different account.

        Returns:
            bool: True if at least one session was successfully authenticated
        """
        if self.multi_account:
            stream_log(f"[{datetime.now().strftime('%H:%M:%S')}] Initializing {self.max_workers} workers with {len(self.credentials)} accounts...")
        else:
            stream_log(f"[{datetime.now().strftime('%H:%M:%S')}] Initializing {self.max_workers} parallel sessions...")

        self.session_pool = create_session_pool(self.max_workers)
        successful_logins = 0

        for i, session_info in enumerate(self.session_pool):
            # Assign credential to worker (round-robin if more workers than accounts)
            cred_index = i % len(self.credentials)
            cred = self.credentials[cred_index]
            username = cred.get('username', '')
            password = cred.get('password', '')
            account_note = cred.get('note', '') or username[-4:]  # Last 4 digits as identifier

            # Store credential info in session_info for later use
            session_info['credential'] = cred
            session_info['account_id'] = account_note

            worker_name = f"Worker {i+1} ({session_info['name']})"
            if self.multi_account:
                worker_name += f" [Acc: {account_note}]"

            try:
                stream_log(f"  {worker_name}: Logging in...")

                session = session_info['session']

                # Get login page first
                response = session.get(self.login_url, timeout=PARALLEL_CONFIG['download']['timeout'])
                response.raise_for_status()

                # Post login with assigned credential
                login_data = {'user': username, 'pass': password}
                response = session.post(
                    self.login_url,
                    data=login_data,
                    timeout=PARALLEL_CONFIG['download']['timeout'],
                    allow_redirects=True
                )
                response.raise_for_status()

                # Verify login by trying to access validation page
                test_url = self.validation_url
                verify_response = session.get(test_url, timeout=60)

                # If redirected back to login or got error page, login failed
                if 'login' in verify_response.url.lower():
                    raise Exception("Redirected back to login page")

                # Check for valid content (should contain tables or download links)
                if verify_response.status_code != 200:
                    raise Exception(f"Validation page returned status {verify_response.status_code}")

                session_info['logged_in'] = True
                successful_logins += 1
                stream_log(f"  {worker_name}: ✓ Login successful", 'success')

                # Small delay between logins
                time.sleep(1)

            except Exception as e:
                stream_log(f"  {worker_name}: ✗ Login failed: {e}", 'error')
                session_info['logged_in'] = False

        stream_log(f"[{datetime.now().strftime('%H:%M:%S')}] {successful_logins}/{self.max_workers} sessions ready")

        # Update progress with worker info
        self._update_progress(
            workers=[{
                'id': i,
                'name': s['name'],
                'status': 'ready' if s.get('logged_in') else 'failed'
            } for i, s in enumerate(self.session_pool)]
        )

        return successful_logins > 0

    def get_download_links(self) -> List[Dict]:
        """Get all download links from validation page using first available session"""
        stream_log(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching download links...")

        # Use first logged-in session
        session = None
        for s in self.session_pool:
            if s.get('logged_in'):
                session = s['session']
                break

        if not session:
            raise Exception("No logged-in session available")

        try:
            response = session.get(self.validation_url, timeout=PARALLEL_CONFIG['download']['timeout'])
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'lxml')
            download_links = []
            tables = soup.find_all('table')

            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    excel_links = row.find_all('a', string=re.compile(r'download excel', re.IGNORECASE))
                    for excel_link in excel_links:
                        excel_href = excel_link.get('href')
                        if excel_href:
                            parsed = urlparse(excel_href)
                            params = parse_qs(parsed.query)

                            filename = None
                            if 'fn' in params:
                                filename = params['fn'][0]
                            elif 'filename' in params:
                                filename = params['filename'][0].replace('.ecd', '.xls')

                            if not filename:
                                filename = f"eclaim_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xls"

                            full_url = urljoin(self.base_url, excel_href)
                            download_links.append({
                                'url': full_url,
                                'filename': filename
                            })

            # Remove duplicates
            unique_links = []
            seen = set()
            for link in download_links:
                if link['filename'] not in seen:
                    unique_links.append(link)
                    seen.add(link['filename'])

            stream_log(f"[{datetime.now().strftime('%H:%M:%S')}] Found {len(unique_links)} files to download")
            return unique_links

        except Exception as e:
            stream_log(f"✗ Error fetching download links: {e}", 'error')
            raise

    def _download_file(self, session_info: Dict, file_info: Dict, file_idx: int, total_files: int) -> Dict:
        """
        Download a single file using the specified session.

        Args:
            session_info: Session information dict with session object
            file_info: File info dict with url and filename
            file_idx: Current file index (1-based)
            total_files: Total number of files

        Returns:
            Dict with download result
        """
        filename = file_info['filename']
        url = file_info['url']
        worker_name = session_info['name']
        worker_id = self.session_pool.index(session_info)

        # Update current file for this worker
        with self.progress_lock:
            self.progress['current_files'][str(worker_id)] = filename

        result = {
            'filename': filename,
            'success': False,
            'skipped': False,
            'error': None,
            'file_size': 0,
            'worker': worker_name,
        }

        # Check if already downloaded
        if self._is_already_downloaded(filename):
            stream_log(f"[{worker_name}] [{file_idx}/{total_files}] Skipping {filename} (already downloaded)")
            result['skipped'] = True
            return result

        # Retry logic
        max_retries = PARALLEL_CONFIG['download']['retry_count']

        for retry in range(max_retries + 1):
            try:
                if retry > 0:
                    delay = PARALLEL_CONFIG['download']['backoff_base'] * (2 ** (retry - 1))
                    delay = min(delay, PARALLEL_CONFIG['download']['backoff_max'])
                    stream_log(f"[{worker_name}] [{file_idx}/{total_files}] Retry {retry}/{max_retries} for {filename} (waiting {delay}s)...", 'warning')
                    time.sleep(delay)
                else:
                    stream_log(f"[{worker_name}] [{file_idx}/{total_files}] Downloading {filename}...")

                # Download file
                session = session_info['session']
                response = session.get(
                    url,
                    timeout=PARALLEL_CONFIG['download']['timeout'],
                    stream=True
                )

                # Check for rate limiting
                if response.status_code in [429, 403]:
                    session_info['error_count'] = session_info.get('error_count', 0) + 1
                    raise Exception(f"Rate limited (HTTP {response.status_code})")

                response.raise_for_status()

                # Save file
                file_path = self.download_dir / filename
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                file_size = file_path.stat().st_size

                # Validate file size
                if file_size < 100:
                    raise Exception(f"File too small ({file_size} bytes)")

                # Success
                result['success'] = True
                result['file_size'] = file_size
                session_info['total_downloads'] = session_info.get('total_downloads', 0) + 1
                session_info['error_count'] = 0

                # Record to history for file listing
                self._record_download(filename, file_size, url)

                stream_log(f"[{worker_name}] [{file_idx}/{total_files}] ✓ Downloaded: {filename} ({file_size:,} bytes)", 'success')

                # Per-file delay
                time.sleep(PARALLEL_CONFIG['download']['per_file_delay'])

                return result

            except Exception as e:
                result['error'] = str(e)

                if retry == max_retries:
                    stream_log(f"[{worker_name}] [{file_idx}/{total_files}] ✗ Failed after {max_retries} retries: {filename}", 'error')
                    stream_log(f"    Error: {e}", 'error')

                    # Rotate session if too many errors
                    if session_info.get('error_count', 0) >= 3:
                        stream_log(f"[{worker_name}] Rotating session due to multiple errors...", 'warning')
                        try:
                            new_session_info = rotate_session(session_info)
                            # Re-login new session
                            new_session = new_session_info['session']
                            new_session.get(self.login_url, timeout=60)
                            new_session.post(
                                self.login_url,
                                data={'user': self.username, 'pass': self.password},
                                timeout=60
                            )
                            # Update session in pool
                            idx = self.session_pool.index(session_info)
                            self.session_pool[idx] = new_session_info
                            stream_log(f"[{worker_name}] → Rotated to {new_session_info['name']}", 'info')
                        except Exception as rotate_err:
                            stream_log(f"[{worker_name}] Failed to rotate session: {rotate_err}", 'error')

        return result

    def download_parallel(self, download_links: List[Dict]) -> Dict:
        """
        Download files in parallel using thread pool.

        Args:
            download_links: List of file info dicts

        Returns:
            Dict with download statistics
        """
        total_files = len(download_links)

        self._update_progress(
            status='downloading',
            total=total_files,
            completed=0,
            failed=0,
            skipped=0,
            start_time=datetime.now().isoformat(),
        )

        stream_log(f"\n[{datetime.now().strftime('%H:%M:%S')}] Starting parallel download ({self.max_workers} workers)...")
        stream_log(f"Total files: {total_files}")
        stream_log("-" * 60)

        # Get available sessions
        available_sessions = [s for s in self.session_pool if s.get('logged_in')]

        if not available_sessions:
            raise Exception("No logged-in sessions available")

        results = []
        completed = 0
        failed = 0
        skipped = 0

        # Use ThreadPoolExecutor for parallel downloads
        with ThreadPoolExecutor(max_workers=len(available_sessions)) as executor:
            # Submit all download tasks
            futures = {}
            for idx, link in enumerate(download_links, 1):
                # Round-robin session assignment
                session = available_sessions[(idx - 1) % len(available_sessions)]
                future = executor.submit(
                    self._download_file,
                    session,
                    link,
                    idx,
                    total_files
                )
                futures[future] = link

            # Process results as they complete
            for future in as_completed(futures):
                result = future.result()
                results.append(result)

                if result['skipped']:
                    skipped += 1
                elif result['success']:
                    completed += 1
                else:
                    failed += 1
                    with self.progress_lock:
                        self.progress['errors'].append({
                            'filename': result['filename'],
                            'error': result['error'],
                            'worker': result['worker'],
                        })

                self._update_progress(
                    completed=completed,
                    failed=failed,
                    skipped=skipped,
                )

        # Final summary
        end_time = datetime.now()
        self._update_progress(
            status='completed',
            end_time=end_time.isoformat(),
            current_files={},
        )

        stream_log("-" * 60)
        stream_log(f"[{end_time.strftime('%H:%M:%S')}] Download completed!")
        stream_log(f"  Downloaded: {completed}")
        stream_log(f"  Skipped: {skipped}")
        stream_log(f"  Failed: {failed}")

        return {
            'total': total_files,
            'completed': completed,
            'skipped': skipped,
            'failed': failed,
            'results': results,
        }

    def run(self) -> Dict:
        """
        Main execution method.

        Returns:
            Dict with overall results
        """
        stream_log("=" * 60)
        stream_log("E-Claim Parallel Downloader")
        stream_log("=" * 60)
        stream_log(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        stream_log(f"Month/Year: {self.month}/{self.year} BE")
        stream_log(f"Scheme: {self.scheme.upper()}")
        stream_log(f"Workers: {self.max_workers}")

        try:
            # Initialize sessions
            if not self.initialize_sessions():
                raise Exception("Failed to initialize any session")

            # Get download links
            download_links = self.get_download_links()

            if not download_links:
                stream_log("No files found to download", 'warning')
                return {'total': 0, 'completed': 0, 'failed': 0, 'skipped': 0}

            # Download in parallel
            results = self.download_parallel(download_links)

            return results

        except Exception as e:
            stream_log(f"✗ Fatal error: {e}", 'error')
            self._update_progress(status='error', error=str(e))
            raise

        finally:
            # Cleanup sessions
            for session_info in self.session_pool:
                try:
                    session_info['session'].close()
                except Exception:
                    pass


def run_parallel_download(
    username: str,
    password: str,
    month: int,
    year: int,
    scheme: str = 'ucs',
    max_workers: int = 3,
    progress_callback: Callable = None
) -> Dict:
    """
    Convenience function to run parallel download.

    Args:
        username: NHSO username
        password: NHSO password
        month: Service month (1-12)
        year: Service year (Buddhist Era)
        scheme: Insurance scheme (ucs, ofc, lgo, sss)
        max_workers: Number of parallel workers
        progress_callback: Optional callback for progress updates

    Returns:
        Dict with download results
    """
    downloader = ParallelDownloader(
        username=username,
        password=password,
        month=month,
        year=year,
        scheme=scheme,
        max_workers=max_workers,
        progress_callback=progress_callback
    )

    return downloader.run()
