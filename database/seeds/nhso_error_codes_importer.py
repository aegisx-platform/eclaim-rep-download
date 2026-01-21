#!/usr/bin/env python3
"""
NHSO Error Codes Importer
Imports error codes from MySQL dump file into PostgreSQL/MySQL database
"""

import os
import re
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.db_pool import get_connection, return_connection
from config.database import get_db_config

def get_db_type():
    """Get the database type from environment or config"""
    import os
    return os.environ.get('DB_TYPE', 'postgresql')


def get_db_connection():
    """Get a database connection (wrapper for compatibility)"""
    return get_connection()


def parse_mysql_dump(file_path):
    """Parse MySQL dump file and extract INSERT data"""
    records = []

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find INSERT statement
    insert_match = re.search(
        r"INSERT INTO `fdh_nhso_error_code`.*?VALUES\s*\n?(.*?);",
        content,
        re.DOTALL | re.IGNORECASE
    )

    if not insert_match:
        print("❌ No INSERT statement found in file")
        return records

    values_str = insert_match.group(1)

    # Parse each row - handle multi-line values
    # Pattern: (id, 'code', 'type', 'description', 'guide', isactive, 'timestamp')
    row_pattern = re.compile(
        r"\((\d+),'([^']*?)','([^']*?)','?(.*?)'?,'?(.*?)'?,(\d+),'([^']+)'\)",
        re.DOTALL
    )

    # Alternative: split by ),\n\t( pattern
    rows = re.split(r'\),\s*\n?\s*\(', values_str)

    for i, row in enumerate(rows):
        # Clean up the row
        row = row.strip()
        if row.startswith('('):
            row = row[1:]
        if row.endswith(')'):
            row = row[:-1]

        try:
            # Parse fields manually to handle complex escaping
            parts = []
            current = ''
            in_quote = False
            escape_next = False

            for char in row:
                if escape_next:
                    current += char
                    escape_next = False
                elif char == '\\':
                    escape_next = True
                    current += char
                elif char == "'" and not in_quote:
                    in_quote = True
                elif char == "'" and in_quote:
                    in_quote = False
                elif char == ',' and not in_quote:
                    parts.append(current.strip())
                    current = ''
                else:
                    current += char

            parts.append(current.strip())  # Add last part

            if len(parts) >= 6:
                record = {
                    'id': int(parts[0]),
                    'code': parts[1].strip("'").replace("\\'", "'"),
                    'type': parts[2].strip("'").replace("\\'", "'"),
                    'description': parts[3].strip("'").replace("\\'", "'").replace('\\n', '\n') if parts[3] != 'NULL' else None,
                    'guide': parts[4].strip("'").replace("\\'", "'").replace('\\n', '\n') if parts[4] != 'NULL' else None,
                    'is_active': int(parts[5]) == 1
                }
                records.append(record)
        except Exception as e:
            print(f"⚠️  Error parsing row {i+1}: {e}")
            continue

    return records


def import_to_postgresql(records, conn):
    """Import records to PostgreSQL"""
    cursor = conn.cursor()

    insert_sql = """
        INSERT INTO nhso_error_codes (id, code, type, description, guide, is_active)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (code) DO UPDATE SET
            type = EXCLUDED.type,
            description = EXCLUDED.description,
            guide = EXCLUDED.guide,
            is_active = EXCLUDED.is_active,
            updated_at = CURRENT_TIMESTAMP
    """

    count = 0
    for record in records:
        try:
            cursor.execute(insert_sql, (
                record['id'],
                record['code'],
                record['type'],
                record['description'],
                record['guide'],
                record['is_active']
            ))
            count += 1
        except Exception as e:
            print(f"⚠️  Error inserting {record['code']}: {e}")

    # Reset sequence to max id
    cursor.execute("SELECT setval('nhso_error_codes_id_seq', (SELECT MAX(id) FROM nhso_error_codes))")

    conn.commit()
    cursor.close()
    return count


def import_to_mysql(records, conn):
    """Import records to MySQL"""
    cursor = conn.cursor()

    insert_sql = """
        INSERT INTO nhso_error_codes (id, code, type, description, guide, is_active)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            type = VALUES(type),
            description = VALUES(description),
            guide = VALUES(guide),
            is_active = VALUES(is_active)
    """

    count = 0
    for record in records:
        try:
            cursor.execute(insert_sql, (
                record['id'],
                record['code'],
                record['type'],
                record['description'],
                record['guide'],
                1 if record['is_active'] else 0
            ))
            count += 1
        except Exception as e:
            print(f"⚠️  Error inserting {record['code']}: {e}")

    conn.commit()
    cursor.close()
    return count


def main():
    """Main entry point"""
    # Default file path
    default_path = os.path.expanduser('~/Downloads/fdh-error-code.sql')

    # Check command line args
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    elif os.path.exists(default_path):
        file_path = default_path
    else:
        # Check in seeds directory for both possible filenames
        seeds_paths = [
            os.path.join(os.path.dirname(__file__), 'nhso_error_codes.sql'),
            os.path.join(os.path.dirname(__file__), 'fdh-error-code.sql'),
        ]

        file_path = None
        for p in seeds_paths:
            if os.path.exists(p):
                file_path = p
                break

        if not file_path:
            print("⚠️  WARNING: NHSO error codes SQL file not found - skipping error codes seed")
            print(f"To import NHSO error codes:")
            print(f"1. Place fdh-error-code.sql or nhso_error_codes.sql in: database/seeds/")
            print(f"2. Run: python database/seeds/nhso_error_codes_importer.py")
            print("Imported: 0")  # For regex parsing in system_api.py
            sys.exit(0)  # Exit success to allow other seeds to continue

    print(f"📂 Reading: {file_path}")

    # Parse the SQL file
    records = parse_mysql_dump(file_path)

    if not records:
        print("❌ No records found in file")
        sys.exit(1)

    print(f"📊 Found {len(records)} error codes")

    # Get database connection
    db_type = get_db_type()
    print(f"🗄️  Database: {db_type}")

    conn = get_db_connection()

    try:
        if db_type == 'postgresql':
            count = import_to_postgresql(records, conn)
        else:
            count = import_to_mysql(records, conn)

        print(f"✅ Imported {count} error codes successfully")

    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
