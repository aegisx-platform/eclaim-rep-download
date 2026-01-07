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
        print(f"[{datetime.now()}] Navigating to login page...")
        page.goto(self.login_url, wait_until='networkidle')

        print(f"[{datetime.now()}] Filling login form...")
        # Fill username and password
        page.fill('input[name="user"]', self.username)
        page.fill('input[name="pass"]', self.password)

        # Submit login
        print(f"[{datetime.now()}] Submitting login...")
        page.click('input[type="submit"]')

        # Wait for navigation after login
        page.wait_for_load_state('networkidle')
        print(f"[{datetime.now()}] Login successful!")

    def get_download_links(self, page):
        """Get all download Excel links from validation page"""
        print(f"[{datetime.now()}] Navigating to validation page...")
        page.goto(self.validation_url, wait_until='networkidle')

        # Wait for table to load
        time.sleep(2)

        print(f"[{datetime.now()}] Extracting download links...")

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
                    # Get the corresponding rep file link for filename reference
                    rep_link = row.locator('a:has-text("rep_eclaim")').first
                    if rep_link.is_visible():
                        rep_href = rep_link.get_attribute('href')
                        # Extract filename from rep link
                        filename = rep_href.split('/')[-1] if rep_href else None

                        if href and filename:
                            download_links.append({
                                'url': href if href.startswith('http') else f"https://eclaim.nhso.go.th{href}",
                                'filename': filename.replace('.ecd', '.xls'),  # Excel extension
                                'row_data': row.inner_text()
                            })
            except Exception as e:
                # Skip rows that don't have download links
                continue

        print(f"[{datetime.now()}] Found {len(download_links)} download links")
        return download_links

    def download_files(self, page, download_links):
        """Download Excel files"""
        downloaded_count = 0
        skipped_count = 0

        for idx, link_info in enumerate(download_links, 1):
            filename = link_info['filename']
            url = link_info['url']

            # Check if already downloaded
            if self._is_already_downloaded(filename):
                print(f"[{idx}/{len(download_links)}] Skipping {filename} (already downloaded)")
                skipped_count += 1
                continue

            try:
                print(f"[{idx}/{len(download_links)}] Downloading {filename}...")

                # Handle download
                with page.expect_download() as download_info:
                    page.goto(url)

                download = download_info.value

                # Save file
                file_path = self.download_dir / filename
                download.save_as(file_path)

                # Record download
                self.download_history['downloads'].append({
                    'filename': filename,
                    'download_date': datetime.now().isoformat(),
                    'file_path': str(file_path),
                    'url': url
                })

                downloaded_count += 1
                print(f"[{idx}/{len(download_links)}] ✓ Downloaded: {filename}")

                # Small delay to avoid overwhelming server
                time.sleep(1)

            except Exception as e:
                print(f"[{idx}/{len(download_links)}] ✗ Error downloading {filename}: {str(e)}")
                continue

        return downloaded_count, skipped_count

    def run(self):
        """Main execution"""
        print("="*60)
        print("E-Claim Excel File Downloader")
        print("="*60)
        print(f"Started at: {datetime.now()}")
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
                downloaded, skipped = self.download_files(page, download_links)

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
                print(f"Downloaded: {downloaded}")
                print(f"Skipped (already downloaded): {skipped}")
                print(f"Download directory: {self.download_dir.absolute()}")
                print(f"Completed at: {datetime.now()}")
                print("="*60)

            except Exception as e:
                print(f"\n✗ Error: {str(e)}")
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
