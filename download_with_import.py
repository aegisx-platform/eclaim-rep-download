#!/usr/bin/env python3
"""
Download with Auto-Import Wrapper
Runs downloader and optionally triggers import after completion
"""

import sys
import subprocess
import argparse
from pathlib import Path
from utils.log_stream import log_streamer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--month', type=int, help='Month to download')
    parser.add_argument('--year', type=int, help='Year to download (BE)')
    parser.add_argument('--auto-import', action='store_true', help='Auto-import after download')
    args = parser.parse_args()

    log_streamer.write_log('🚀 Starting download process...', 'info', 'download')

    # Build download command
    download_cmd = [sys.executable, 'eclaim_downloader_http.py']
    if args.month:
        download_cmd.extend(['--month', str(args.month)])
        log_streamer.write_log(f'📅 Target: Month {args.month}, Year {args.year} BE', 'info', 'download')
    if args.year:
        download_cmd.extend(['--year', str(args.year)])

    # Add --import-each flag if auto-import is enabled
    if args.auto_import:
        download_cmd.append('--import-each')
        log_streamer.write_log('⚡ Concurrent import mode: ENABLED', 'info', 'system')

    # Run downloader with real-time output streaming
    try:
        log_streamer.write_log('⬇️ Downloading files from e-claim system...', 'info', 'download')

        # Use Popen to stream output in real-time
        process = subprocess.Popen(
            download_cmd,
            cwd=Path(__file__).parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # Line buffered
            universal_newlines=True
        )

        # Stream output line by line in real-time
        for line in process.stdout:
            if line.strip():
                # Determine log level based on content
                line_lower = line.lower()
                if '✓' in line or 'success' in line_lower or 'completed' in line_lower:
                    level = 'success'
                elif '✗' in line or 'error' in line_lower or 'failed' in line_lower:
                    level = 'error'
                elif 'downloading' in line_lower or 'found' in line_lower:
                    level = 'info'
                else:
                    level = 'info'

                log_streamer.write_log(line.strip(), level, 'download')

        # Wait for process to complete
        process.wait()

        if process.returncode == 0:
            log_streamer.write_log('✅ Download completed successfully!', 'success', 'download')

            # Note: Import happens concurrently during download if --auto-import is enabled
            if args.auto_import:
                log_streamer.write_log('✅ Concurrent import completed!', 'success', 'import')

        else:
            log_streamer.write_log(f'❌ Download failed with code {process.returncode}', 'error', 'download')
            sys.exit(process.returncode)

    except Exception as e:
        log_streamer.write_log(f'❌ Download error: {str(e)}', 'error', 'download')
        sys.exit(1)

    log_streamer.write_log('🎉 Process completed!', 'success', 'system')


if __name__ == '__main__':
    main()
