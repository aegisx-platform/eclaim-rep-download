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

    # Run downloader
    try:
        log_streamer.write_log('⬇️ Downloading files from e-claim system...', 'info', 'download')
        result = subprocess.run(
            download_cmd,
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True
        )

        # Log download output line by line
        for line in result.stdout.splitlines():
            if line.strip():
                log_streamer.write_log(line, 'info', 'download')

        if result.returncode == 0:
            log_streamer.write_log('✅ Download completed successfully!', 'success', 'download')

            # Auto-import if requested
            if args.auto_import:
                log_streamer.write_log('🔄 Starting auto-import...', 'info', 'import')

                import_cmd = [sys.executable, 'eclaim_import.py', '--directory', 'downloads']

                try:
                    log_streamer.write_log('📥 Importing files to database...', 'info', 'import')
                    import_result = subprocess.run(
                        import_cmd,
                        cwd=Path(__file__).parent,
                        capture_output=True,
                        text=True
                    )

                    # Log import output
                    for line in import_result.stdout.splitlines():
                        if line.strip():
                            log_streamer.write_log(line, 'info', 'import')

                    if import_result.returncode == 0:
                        log_streamer.write_log('✅ Auto-import completed successfully!', 'success', 'import')
                    else:
                        log_streamer.write_log(f'❌ Import failed with code {import_result.returncode}', 'error', 'import')
                        if import_result.stderr:
                            log_streamer.write_log(import_result.stderr, 'error', 'import')

                except Exception as e:
                    log_streamer.write_log(f'❌ Import error: {str(e)}', 'error', 'import')

        else:
            log_streamer.write_log(f'❌ Download failed with code {result.returncode}', 'error', 'download')
            if result.stderr:
                log_streamer.write_log(result.stderr, 'error', 'download')
            sys.exit(result.returncode)

    except Exception as e:
        log_streamer.write_log(f'❌ Download error: {str(e)}', 'error', 'download')
        sys.exit(1)

    log_streamer.write_log('🎉 Process completed!', 'success', 'system')


if __name__ == '__main__':
    main()
