#!/usr/bin/env python3
"""
Test Audit Logging System

Verifies that audit logging is working correctly:
1. Table exists
2. Can insert audit events
3. Views are working
4. Triggers prevent modification
5. Queries return expected data

Run after migrations: python test_audit_log.py
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.audit_logger import audit_logger
from config.db_pool import get_connection, return_connection
from config.database import DB_TYPE


def test_table_exists():
    """Test that audit_log table exists."""
    print("Testing: audit_log table exists...")

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        if DB_TYPE == 'postgresql':
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'audit_log'
                )
            """)
            exists = cursor.fetchone()[0]
        else:  # MySQL
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_name = 'audit_log'
                  AND table_schema = DATABASE()
            """)
            exists = cursor.fetchone()[0] > 0

        if exists:
            print("✓ audit_log table exists")
            return True
        else:
            print("✗ audit_log table NOT found")
            return False

    finally:
        if cursor:
            cursor.close()
        if conn:
            return_connection(conn)


def test_insert_audit_event():
    """Test inserting audit events."""
    print("\nTesting: Insert audit events...")

    # Test 1: Simple create event
    audit_id = audit_logger.log(
        action=audit_logger.ACTION_CREATE,
        resource_type='test_resource',
        resource_id='TEST-001',
        user_id='test_user',
        ip_address='127.0.0.1'
    )

    if audit_id:
        print(f"✓ Inserted CREATE event (ID: {audit_id})")
    else:
        print("✗ Failed to insert CREATE event")
        return False

    # Test 2: Update event with old/new data
    audit_id = audit_logger.log(
        action=audit_logger.ACTION_UPDATE,
        resource_type='test_resource',
        resource_id='TEST-001',
        user_id='test_user',
        old_data={'status': 'pending', 'amount': 100},
        new_data={'status': 'approved', 'amount': 100},
        changes_summary='Approved claim',
        ip_address='127.0.0.1',
        metadata={'reason': 'Test update'}
    )

    if audit_id:
        print(f"✓ Inserted UPDATE event (ID: {audit_id})")
    else:
        print("✗ Failed to insert UPDATE event")
        return False

    # Test 3: Login event
    audit_id = audit_logger.log_login(
        user_id='test_user',
        success=True,
        ip_address='127.0.0.1',
        user_agent='Test Agent'
    )

    if audit_id:
        print(f"✓ Inserted LOGIN event (ID: {audit_id})")
    else:
        print("✗ Failed to insert LOGIN event")
        return False

    # Test 4: Failed login
    audit_id = audit_logger.log_login(
        user_id='attacker',
        success=False,
        ip_address='192.168.1.100',
        error_message='Invalid credentials'
    )

    if audit_id:
        print(f"✓ Inserted LOGIN_FAILED event (ID: {audit_id})")
    else:
        print("✗ Failed to insert LOGIN_FAILED event")
        return False

    # Test 5: Data export (CRITICAL for PDPA)
    audit_id = audit_logger.log_data_export(
        resource_type='claims',
        user_id='test_user',
        ip_address='127.0.0.1',
        record_count=1000,
        export_format='excel',
        filename='claims_export_20260117.xlsx'
    )

    if audit_id:
        print(f"✓ Inserted EXPORT event (ID: {audit_id})")
    else:
        print("✗ Failed to insert EXPORT event")
        return False

    return True


def test_views():
    """Test that audit log views work."""
    print("\nTesting: Audit log views...")

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Test 1: audit_log_stats view
        cursor.execute("SELECT * FROM audit_log_stats")
        stats = cursor.fetchone()

        if stats:
            print(f"✓ audit_log_stats view works")
            print(f"  - Total events: {stats[0]}")
            print(f"  - Unique users: {stats[1]}")
            print(f"  - Failed events: {stats[3]}")
        else:
            print("✗ audit_log_stats view failed")
            return False

        # Test 2: user_activity_summary view
        cursor.execute("SELECT * FROM user_activity_summary LIMIT 5")
        users = cursor.fetchall()

        if users:
            print(f"✓ user_activity_summary view works ({len(users)} users)")
        else:
            print("✓ user_activity_summary view works (no users yet)")

        # Test 3: security_events view
        cursor.execute("SELECT * FROM security_events LIMIT 5")
        events = cursor.fetchall()

        if events:
            print(f"✓ security_events view works ({len(events)} events)")
        else:
            print("✓ security_events view works (no security events)")

        return True

    finally:
        if cursor:
            cursor.close()
        if conn:
            return_connection(conn)


def test_immutability():
    """Test that audit logs cannot be modified."""
    print("\nTesting: Audit log immutability...")

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get a test record
        cursor.execute("SELECT id FROM audit_log LIMIT 1")
        result = cursor.fetchone()

        if not result:
            print("⚠ No records to test (insert some first)")
            return True

        audit_id = result[0]

        # Test 1: Try to UPDATE (should fail)
        try:
            cursor.execute(
                "UPDATE audit_log SET action = 'HACKED' WHERE id = %s",
                (audit_id,)
            )
            conn.commit()
            print("✗ UPDATE should have been blocked!")
            return False
        except Exception as e:
            conn.rollback()
            if 'cannot be modified' in str(e).lower() or 'immutable' in str(e).lower():
                print("✓ UPDATE correctly blocked by trigger")
            else:
                print(f"✓ UPDATE blocked (error: {e})")

        # Test 2: Try to DELETE (should fail)
        try:
            cursor.execute(
                "DELETE FROM audit_log WHERE id = %s",
                (audit_id,)
            )
            conn.commit()
            print("✗ DELETE should have been blocked!")
            return False
        except Exception as e:
            conn.rollback()
            if 'cannot be deleted' in str(e).lower() or 'immutable' in str(e).lower():
                print("✓ DELETE correctly blocked by trigger")
            else:
                print(f"✓ DELETE blocked (error: {e})")

        return True

    finally:
        if cursor:
            cursor.close()
        if conn:
            return_connection(conn)


def test_user_activity():
    """Test getting user activity."""
    print("\nTesting: Get user activity...")

    activity = audit_logger.get_user_activity('test_user', days=30)

    if activity:
        print(f"✓ Retrieved {len(activity)} activities for test_user")
        print(f"  - Latest: {activity[0]['action']} on {activity[0]['resource_type']}")
        return True
    else:
        print("✓ No activity found (expected if no test_user events)")
        return True


def main():
    """Run all tests."""
    print("="*60)
    print("AUDIT LOG SYSTEM TEST")
    print("="*60)
    print(f"Database: {DB_TYPE}")
    print()

    tests = [
        ("Table exists", test_table_exists),
        ("Insert events", test_insert_audit_event),
        ("Views work", test_views),
        ("Immutability", test_immutability),
        ("User activity", test_user_activity),
    ]

    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"✗ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nResult: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Audit logging is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please check the output above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
