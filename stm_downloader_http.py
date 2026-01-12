#!/usr/bin/env python3
"""
E-Claim Statement (STM) File Downloader (HTTP Client Version)
Automatically downloads Statement Excel files from NHSO e-claim system
Supports UCS, OFC, SSS, LGO schemes

Statement Types:
- IP (ผู้ป่วยใน)
- OP (ผู้ป่วยนอก)
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

# Direct log writing for real-time logs
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
            'source': 'stm_download',
            'message': message
        }
        with open(REALTIME_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json_module.dumps(log_entry) + '\n')
    except Exception:
        pass


class STMDownloader:
    """Statement (STM) File Downloader - UCS Only"""

    # Statement URL - UCS only (NHSO only provides UCS Statement)
    STATEMENT_URL = {
        'list': '/webComponent/ucs/statementUCSAction.do',
        'view': '/webComponent/ucs/statementUCSViewAction.do',
        'name': 'UC Statement (หลักประกันสุขภาพถ้วนหน้า)'
    }

    # Person types
    PERSON_TYPES = {
        'ip': {'code': '1', 'name': 'ผู้ป่วยใน (IP)'},
        'op': {'code': '2', 'name': 'ผู้ป่วยนอก (OP)'},
        'all': {'code': '', 'name': 'ทั้งหมด'}
    }

    def __init__(self, year=None, month=None, person_type='all'):
        """
        Initialize STM Downloader (UCS Statement only)

        Args:
            year (int, optional): Fiscal year in Buddhist Era. Defaults to current fiscal year.
            month (int, optional): Month (1-12). None = all months.
            person_type (str): Patient type (ip, op, all). Defaults to 'all'.
        """
        self.username, self.password = self._load_credentials()
        self.download_dir = Path(os.getenv('DOWNLOAD_DIR', './downloads')) / 'stm'
        self.tracking_file = Path('stm_download_history.json')
        self.person_type = person_type.lower()

        # Set year and month
        now = datetime.now()
        current_fiscal_year = now.year + 543 if now.month >= 10 else now.year + 542
        self.year = year if year is not None else current_fiscal_year
        self.month = month  # None = all months

        # URLs - UCS Statement only
        self.base_url = 'https://eclaim.nhso.go.th'
        self.login_url = f'{self.base_url}/webComponent/login/LoginAction.do'
        self.list_url = f'{self.base_url}{self.STATEMENT_URL["list"]}'
        self.view_url = f'{self.base_url}{self.STATEMENT_URL["view"]}'
        self.scheme_name = self.STATEMENT_URL['name']

        # Create session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'th,en-US;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })

        # Create download directory
        self.download_dir.mkdir(parents=True, exist_ok=True)

        # Load download history
        self.download_history = self._load_history()

    def _load_credentials(self):
        """Load credentials from settings file or environment variables"""
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

        username = os.getenv('ECLAIM_USERNAME', '').strip()
        password = os.getenv('ECLAIM_PASSWORD', '').strip()

        if not username or not password:
            raise ValueError(
                "E-Claim credentials not configured!\n"
                "Configure via Web UI Settings or environment variables."
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
        for d in self.download_history['downloads']:
            if d['filename'] == filename and d.get('scheme', 'ucs') == 'ucs':
                return True
        return False

    def login(self):
        """Login to e-claim system"""
        stream_log(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Logging in...")

        try:
            # Get login page
            response = self.session.get(self.login_url, timeout=120)
            response.raise_for_status()

            # Post login
            login_data = {
                'user': self.username,
                'pass': self.password
            }

            response = self.session.post(
                self.login_url,
                data=login_data,
                timeout=120,
                allow_redirects=True
            )
            response.raise_for_status()

            if 'login' in response.url.lower() and 'error' in response.text.lower():
                raise Exception("Login failed - invalid credentials")

            stream_log(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Login successful!", 'success')
            return True

        except Exception as e:
            stream_log(f"✗ Login error: {str(e)}", 'error')
            raise

    def get_statement_list(self):
        """Get list of available statements from AJAX endpoint"""
        stream_log(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Fetching statement list...")
        stream_log(f"  Scheme: {self.scheme_name}")
        stream_log(f"  Year: {self.year}")
        stream_log(f"  Month: {self.month if self.month else 'All'}")
        stream_log(f"  Type: {self.PERSON_TYPES.get(self.person_type, {}).get('name', 'All')}")

        try:
            # First access the main page to get session
            response = self.session.get(self.list_url, timeout=120)
            response.raise_for_status()

            # Convert Buddhist year to Gregorian for API
            gregorian_year = self.year - 543

            # Build AJAX request parameters
            params = {
                'PAGE_HEAD': '',
                'year': str(gregorian_year),
                'month': str(self.month) if self.month else '',
                'person_type': self.PERSON_TYPES.get(self.person_type, {}).get('code', ''),
                'period_no': ''
            }

            # Fetch statement list via AJAX
            self.session.headers.update({
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'text/html, */*; q=0.01'
            })

            response = self.session.get(self.view_url, params=params, timeout=120)
            response.raise_for_status()

            # Parse HTML response
            soup = BeautifulSoup(response.content, 'lxml')

            statements = []

            # Find table with id="table-detail"
            table = soup.find('table', id='table-detail')
            if not table:
                table = soup.find('table')

            if table:
                rows = table.find('tbody').find_all('tr') if table.find('tbody') else table.find_all('tr')

                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 9:
                        try:
                            # Extract statement info from cells
                            period_no = cells[0].get_text(strip=True)
                            issue_date = cells[1].get_text(strip=True)
                            service_month = cells[2].get_text(strip=True)
                            stmt_type = cells[3].get_text(strip=True)  # ผู้ป่วยใน / ผู้ป่วยนอก
                            stmt_period = cells[4].get_text(strip=True)
                            send_date = cells[5].get_text(strip=True)
                            stmt_no = cells[6].get_text(strip=True)  # e.g., 10670_IPUCS256710_01
                            vendor_code = cells[7].get_text(strip=True)

                            # Find download link and extract parameters from onclick
                            download_cell = cells[8] if len(cells) > 8 else None
                            download_params = None

                            if download_cell:
                                link = download_cell.find('a')
                                if link:
                                    onclick = link.get('onclick', '')
                                    # Parse: downloadBill('10670_IPUCS256710_01', '2', '10670', '10670 รพ.ขอนแก่น', '4000 ขอนแก่น', '', '');
                                    match = re.search(r"downloadBill\('([^']*)',\s*'([^']*)',\s*'([^']*)',\s*'([^']*)',\s*'([^']*)',\s*'([^']*)',\s*'([^']*)'\)", onclick)
                                    if match:
                                        download_params = {
                                            'document_no': match.group(1),
                                            'person_type': match.group(2),  # 1=OP, 2=IP
                                            'hcode': match.group(3),
                                            'hname': match.group(4),
                                            'province_name': match.group(5),
                                            'datesend_from': match.group(6),
                                            'datesend_to': match.group(7)
                                        }

                            if download_params:
                                statements.append({
                                    'period_no': period_no,
                                    'issue_date': issue_date,
                                    'service_month': service_month,
                                    'type': stmt_type,
                                    'stmt_period': stmt_period,
                                    'send_date': send_date,
                                    'stmt_no': stmt_no,
                                    'vendor_code': vendor_code,
                                    'download_params': download_params
                                })
                        except Exception as e:
                            stream_log(f"  Warning: Error parsing row: {str(e)}", 'warning')
                            continue

            stream_log(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Found {len(statements)} statements")
            return statements

        except Exception as e:
            stream_log(f"✗ Error fetching statement list: {str(e)}", 'error')
            raise

    def download_statement(self, download_params, stmt_info):
        """Download a single statement file via POST form submission"""
        try:
            document_no = download_params['document_no']
            filename = f"STM_{document_no}.xls"

            # Check if already downloaded
            if self._is_already_downloaded(filename):
                stream_log(f"  ⏭ Skipping (already downloaded): {filename}")
                return None

            stream_log(f"  ⬇ Downloading: {filename}")

            # Build download URL - UCS only
            download_url = f'{self.base_url}/webComponent/ucs/statementUCSDownloadAction.do'

            # POST form data
            form_data = {
                'document_no': download_params['document_no'],
                'person_type': download_params['person_type'],
                'hcode': download_params['hcode'],
                'hname': download_params['hname'],
                'province_name': download_params['province_name'],
                'datesend_from': download_params.get('datesend_from', ''),
                'datesend_to': download_params.get('datesend_to', '')
            }

            response = self.session.post(download_url, data=form_data, timeout=300)
            response.raise_for_status()

            # Check if response is actually a file (not HTML error)
            content_type = response.headers.get('Content-Type', '')
            if 'html' in content_type.lower() and len(response.content) < 1000:
                stream_log(f"  ⚠ Received HTML instead of file, might be error page", 'warning')

            # Save file
            file_path = self.download_dir / filename
            with open(file_path, 'wb') as f:
                f.write(response.content)

            # Record download
            self.download_history['downloads'].append({
                'filename': filename,
                'document_no': document_no,
                'scheme': 'ucs',
                'year': self.year,
                'month': self.month,
                'stmt_type': stmt_info.get('type', ''),
                'service_month': stmt_info.get('service_month', ''),
                'downloaded_at': datetime.now().isoformat(),
                'size': len(response.content)
            })
            self._save_history()

            stream_log(f"  ✓ Downloaded: {filename} ({len(response.content)} bytes)", 'success')
            return str(file_path)

        except Exception as e:
            stream_log(f"  ✗ Download error: {str(e)}", 'error')
            return None

    def download_all(self):
        """Download all available statements"""
        stream_log("=" * 60)
        stream_log(f"STM Downloader - {self.scheme_name}")
        stream_log(f"Year: {self.year}, Month: {self.month if self.month else 'All'}")
        stream_log("=" * 60)

        # Login
        self.login()

        # Get statement list
        statements = self.get_statement_list()

        if not statements:
            stream_log("No statements found to download.")
            return []

        downloaded_files = []
        skipped = 0
        errors = 0

        for stmt in statements:
            stream_log(f"\n[Statement] {stmt['stmt_no']} - {stmt['type']} - {stmt['service_month']}")

            download_params = stmt.get('download_params')
            if download_params:
                result = self.download_statement(download_params, stmt)
                if result:
                    downloaded_files.append(result)
                elif result is None:
                    skipped += 1
                else:
                    errors += 1
            else:
                stream_log(f"  ⚠ No download params found for {stmt['stmt_no']}", 'warning')
                errors += 1

            time.sleep(0.5)  # Rate limiting

        # Update last run
        self.download_history['last_run'] = datetime.now().isoformat()
        self._save_history()

        stream_log("\n" + "=" * 60)
        stream_log(f"Download Complete!")
        stream_log(f"  Downloaded: {len(downloaded_files)} files")
        stream_log(f"  Skipped: {skipped} files")
        stream_log(f"  Errors: {errors}")
        stream_log("=" * 60)

        return downloaded_files

    def run(self):
        """Main entry point"""
        try:
            return self.download_all()
        except Exception as e:
            stream_log(f"✗ Fatal error: {str(e)}", 'error')
            raise


def main():
    """CLI Entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='E-Claim UC Statement Downloader (UCS only)')
    parser.add_argument('--year', type=int, help='Fiscal year (Buddhist Era)')
    parser.add_argument('--month', type=int, help='Month (1-12)')
    parser.add_argument('--type', dest='person_type', default='all',
                        choices=['ip', 'op', 'all'], help='Patient type')
    # --scheme is kept for backward compatibility but ignored
    parser.add_argument('--scheme', help='(Deprecated - only UCS is supported)')

    args = parser.parse_args()

    downloader = STMDownloader(
        year=args.year,
        month=args.month,
        person_type=args.person_type
    )

    downloader.run()


if __name__ == '__main__':
    main()
