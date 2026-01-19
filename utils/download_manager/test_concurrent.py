"""
Test script for concurrent download sessions

Simulates REP and STM downloads running simultaneously
"""

import time
import threading
from datetime import datetime

from utils.download_manager import get_download_manager
from utils.download_manager.models import SessionStatus


def simulate_download(source_type: str, total_files: int, delay: float = 0.1):
    """
    Simulate a download process

    Args:
        source_type: Source type (rep, stm, smt)
        total_files: Total number of files to "download"
        delay: Delay per file in seconds
    """
    manager = get_download_manager()

    try:
        # Create session
        session_id = manager.create_session(source_type, {
            'fiscal_year': 2569,
            'service_month': 1
        })

        print(f"[{source_type.upper()}] Session created: {session_id[:8]}...")

        # Start discovery phase
        print(f"[{source_type.upper()}] Discovering files...")
        manager.update_progress(
            session_id,
            status=SessionStatus.DISCOVERING
        )
        time.sleep(delay * 5)  # Simulate discovery

        # Discovery complete
        already_downloaded = int(total_files * 0.8)  # 80% already exist
        to_download = total_files - already_downloaded

        manager.update_progress(
            session_id,
            status=SessionStatus.DOWNLOADING,
            total_discovered=total_files,
            already_downloaded=already_downloaded,
            to_download=to_download,
            discovery_completed=True,
            started_at=datetime.now()
        )

        print(f"[{source_type.upper()}] Found {total_files} files ({to_download} to download, {already_downloaded} skip)")

        # Download phase
        for i in range(total_files):
            if i < already_downloaded:
                # Skip existing file
                manager.update_progress(
                    session_id,
                    processed=i + 1,
                    skipped=i + 1,
                    current_file=f"{source_type}_file_{i:03d}.xls"
                )
            else:
                # Download new file
                manager.update_progress(
                    session_id,
                    processed=i + 1,
                    downloaded=(i - already_downloaded + 1),
                    skipped=already_downloaded,
                    current_file=f"{source_type}_file_{i:03d}.xls"
                )

            time.sleep(delay)

            # Progress report every 20%
            if (i + 1) % max(1, total_files // 5) == 0:
                progress = manager.get_progress(session_id)
                print(f"[{source_type.upper()}] {progress.processed}/{progress.total_discovered} files ({progress.progress_percent:.1f}%)")

        # Complete
        manager.complete_session(session_id)
        progress = manager.get_progress(session_id)
        print(f"[{source_type.upper()}] ✓ Complete: {progress.downloaded} new, {progress.skipped} skipped")

    except Exception as e:
        print(f"[{source_type.upper()}] ✗ Error: {e}")
        import traceback
        traceback.print_exc()


def test_concurrent_downloads():
    """Test concurrent REP and STM downloads"""
    print("=" * 70)
    print("Testing Concurrent Downloads (REP + STM)")
    print("=" * 70)
    print()

    # Create threads for concurrent downloads
    rep_thread = threading.Thread(
        target=simulate_download,
        args=('rep', 100, 0.05),
        name='REP-Downloader'
    )

    stm_thread = threading.Thread(
        target=simulate_download,
        args=('stm', 50, 0.08),
        name='STM-Downloader'
    )

    # Start both threads
    print("Starting concurrent downloads...")
    print()

    rep_thread.start()
    time.sleep(0.5)  # Small delay for clearer logs
    stm_thread.start()

    # Monitor active sessions
    manager = get_download_manager()
    while rep_thread.is_alive() or stm_thread.is_alive():
        active = manager.get_active_sessions()
        if active:
            print(f"\n[MONITOR] Active: {len(active)} sessions")
            for p in active:
                print(f"  - {p.source_type.upper()}: {p.processed}/{p.total_discovered} ({p.progress_percent:.1f}%)")

        time.sleep(2)

    # Wait for completion
    rep_thread.join()
    stm_thread.join()

    print()
    print("=" * 70)
    print("✓ Test Complete - Both downloads finished")
    print("=" * 70)


def test_session_blocking():
    """Test that duplicate sessions are blocked"""
    print("=" * 70)
    print("Testing Session Blocking")
    print("=" * 70)
    print()

    manager = get_download_manager()

    # Create REP session
    print("1. Creating REP session...")
    session1 = manager.create_session('rep', {'fiscal_year': 2569})
    print(f"   ✓ Session created: {session1[:8]}...")

    # Try to create another REP session
    print("\n2. Trying to create another REP session...")
    try:
        session2 = manager.create_session('rep', {'fiscal_year': 2569})
        print(f"   ✗ FAILED: Should have blocked duplicate session!")
    except ValueError as e:
        print(f"   ✓ Correctly blocked: {e}")

    # Create STM session (different source)
    print("\n3. Creating STM session (different source)...")
    session3 = manager.create_session('stm', {'fiscal_year': 2569})
    print(f"   ✓ Session created: {session3[:8]}...")

    # Check active
    print("\n4. Active sessions:")
    active = manager.get_active_sessions()
    for p in active:
        print(f"   - {p.source_type.upper()}: {p.session_id[:8]}...")

    # Cancel and retry
    print("\n5. Cancelling REP session...")
    manager.cancel_session(session1)
    print("   ✓ Cancelled")

    print("\n6. Creating new REP session (should work now)...")
    session4 = manager.create_session('rep', {'fiscal_year': 2569})
    print(f"   ✓ Session created: {session4[:8]}...")

    print()
    print("=" * 70)
    print("✓ Session Blocking Test Complete")
    print("=" * 70)


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'concurrent':
        test_concurrent_downloads()
    elif len(sys.argv) > 1 and sys.argv[1] == 'blocking':
        test_session_blocking()
    else:
        print("Usage:")
        print("  python test_concurrent.py concurrent  # Test concurrent downloads")
        print("  python test_concurrent.py blocking    # Test session blocking")
