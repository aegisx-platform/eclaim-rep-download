#!/usr/bin/env python3
"""
E-Claim Excel File Downloader
Automatically downloads Excel files from NHSO e-claim validation page
"""

import os
import json
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# Load environment variables
load_dotenv()

class EClaimDownloader:
    def __init__(self):
        self.username = os.getenv('ECLAIM_USERNAME')
        self.password = os.getenv('ECLAIM_PASSWORD')
        self.download_dir = Path(os.getenv('DOWNLOAD_DIR', './downloads'))
        self.tracking_file = Path('download_history.json')
        self.login_url = 'https://eclaim.nhso.go.th/webComponent/login/LoginAction.do'
        self.validation_url = 'https://eclaim.nhso.go.th/webComponent/validation/ValidationMainAction.do?maininscl=ucs'

        # Create download directory
        self.download_dir.mkdir(exist_ok=True)

        # Load download history
        self.download_history = self._load_history()

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
            json.dump(self.download_history, {}, ensure_ascii=False, indent=2)

    def _is_already_downloaded(self, filename):
        """Check if file was already downloaded"""
        return any(d['filename'] == filename for d in self.download_history['downloads'])

    def login(self, page):
        """Login to e-claim system"""
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Navigating to login page...")
        page.goto(self.login_url, wait_until='networkidle')

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Filling login form...")
        # Fill username and password
        page.fill('input[name="user"]', self.username)
        page.fill('input[name="pass"]', self.password)

        # Submit login
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Submitting login...")
        page.click('input[type="submit"]')

        # Wait for navigation after login
        page.wait_for_load_state('networkidle')
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Login successful!")

    def get_download_links(self, page):
        """Get all download Excel links from validation page"""
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Navigating to validation page...")
        page.goto(self.validation_url, wait_until='networkidle')

        # Wait for table to load
        time.sleep(3)

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Extracting download links...")

        # Get all download excel links
        download_links = []

        # Find all rows in the table
        rows = page.locator('table tr').all()

        for row in rows:
            try:
                # Look for "download excel" link in the row
                excel_link = row.locator('a:has-text("download excel")').first
                if excel_link.is_visible():
                    href = excel_link.get_attribute('href')

                    # Extract filename from URL parameter 'fn'
                    from urllib.parse import urlparse, parse_qs
                    parsed = urlparse(href) if href else None
                    filename = None

                    if parsed:
                        params = parse_qs(parsed.query)
                        if 'fn' in params:
                            filename = params['fn'][0]
                        elif 'file' in params:
                            filename = params['file'][0]

                    # If no filename from URL, try rep link
                    if not filename:
                        rep_link = row.locator('a:has-text("rep_eclaim")').first
                        if rep_link.is_visible():
                            rep_href = rep_link.get_attribute('href')
                            if rep_href:
                                filename = rep_href.split('/')[-1].replace('.ecd', '.xls')

                    if href and filename:
                        full_url = href if href.startswith('http') else f"https://eclaim.nhso.go.th{href}"
                        download_links.append({
                            'url': full_url,
                            'filename': filename
                        })
            except Exception as e:
                # Skip rows that don't have download links
                continue

        # Remove duplicates
        unique_links = []
        seen_filenames = set()
        for link in download_links:
            if link['filename'] not in seen_filenames:
                unique_links.append(link)
                seen_filenames.add(link['filename'])

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Found {len(unique_links)} unique download links")
        return unique_links

    def download_files(self, page, download_links):
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
                        time.sleep(2)
                    else:
                        print(f"[{idx}/{len(download_links)}] Downloading {filename}...")

                    # Handle download with increased timeout (120 seconds)
                    with page.expect_download(timeout=120000) as download_info:
                        page.goto(url, timeout=120000)

                    download = download_info.value

                    # Save file
                    file_path = self.download_dir / filename
                    download.save_as(file_path)

                    # Check file size
                    file_size = file_path.stat().st_size
                    if file_size < 100:
                        raise Exception(f"Downloaded file too small ({file_size} bytes)")

                    # Record download
                    self.download_history['downloads'].append({
                        'filename': filename,
                        'download_date': datetime.now().isoformat(),
                        'file_path': str(file_path),
                        'file_size': file_size,
                        'url': url
                    })

                    downloaded_count += 1
                    print(f"[{idx}/{len(download_links)}] ✓ Downloaded: {filename} ({file_size:,} bytes)")
                    success = True

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
        print("E-Claim Excel File Downloader (Playwright)")
        print("="*60)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        with sync_playwright() as p:
            # Launch browser (headless=False to see what's happening)
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                accept_downloads=True,
                viewport={'width': 1920, 'height': 1080}
            )
            page = context.new_page()

            try:
                # Login
                self.login(page)

                # Get download links
                download_links = self.get_download_links(page)

                if not download_links:
                    print("No download links found!")
                    return

                # Download files
                downloaded, skipped, errors = self.download_files(page, download_links)

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

            finally:
                # Close browser
                browser.close()

def main():
    """Entry point"""
    downloader = EClaimDownloader()
    downloader.run()

if __name__ == '__main__':
    main()
