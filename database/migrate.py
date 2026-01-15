#!/usr/bin/env python3
"""
Database Migration System for E-Claim
Supports both PostgreSQL and MySQL with automatic detection.

Usage:
    python database/migrate.py              # Run all pending migrations
    python database/migrate.py --status     # Show migration status
    python database/migrate.py --seed       # Run seed data
    python database/migrate.py --reset      # Reset and re-run all migrations (DANGER!)
"""

import os
import sys
import argparse
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.database import get_db_config, DB_TYPE


class MigrationRunner:
    """Handles database migrations for PostgreSQL and MySQL."""

    MIGRATIONS_DIR = Path(__file__).parent / 'migrations'
    SEEDS_DIR = Path(__file__).parent / 'seeds'

    def __init__(self):
        self.db_type = DB_TYPE
        self.conn = None
        self.cursor = None

    def connect(self):
        """Establish database connection based on DB_TYPE."""
        config = get_db_config()

        if self.db_type == 'postgresql':
            import psycopg2
            self.conn = psycopg2.connect(**config)
        else:  # mysql
            import pymysql
            self.conn = pymysql.connect(**config)

        self.cursor = self.conn.cursor()
        print(f"[migrate] Connected to {self.db_type} database")

    def close(self):
        """Close database connection."""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    def ensure_migrations_table(self):
        """Create migrations tracking table if not exists."""
        if self.db_type == 'postgresql':
            sql = """
            CREATE TABLE IF NOT EXISTS _migrations (
                id SERIAL PRIMARY KEY,
                version VARCHAR(50) NOT NULL UNIQUE,
                name VARCHAR(255) NOT NULL,
                checksum VARCHAR(64),
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                execution_time_ms INTEGER
            )
            """
        else:  # mysql
            sql = """
            CREATE TABLE IF NOT EXISTS _migrations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                version VARCHAR(50) NOT NULL UNIQUE,
                name VARCHAR(255) NOT NULL,
                checksum VARCHAR(64),
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                execution_time_ms INTEGER
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """

        self.cursor.execute(sql)
        self.conn.commit()

    def get_applied_migrations(self) -> List[str]:
        """Get list of already applied migration versions."""
        self.cursor.execute("SELECT version FROM _migrations ORDER BY version")
        return [row[0] for row in self.cursor.fetchall()]

    def get_migration_files(self) -> List[Tuple[str, Path]]:
        """
        Get list of migration files for current DB type.
        Returns list of (version, filepath) tuples sorted by version.
        """
        migrations = []
        migration_dir = self.MIGRATIONS_DIR / self.db_type

        if not migration_dir.exists():
            print(f"[migrate] Warning: Migration directory not found: {migration_dir}")
            return migrations

        for f in sorted(migration_dir.glob('*.sql')):
            # Extract version from filename (e.g., '001_initial_schema.sql' -> '001')
            version = f.stem.split('_')[0]
            migrations.append((version, f))

        return migrations

    def get_seed_files(self) -> List[Tuple[str, Path]]:
        """
        Get list of seed files for current DB type.
        Returns list of (version, filepath) tuples sorted by version.
        """
        seeds = []
        seed_dir = self.SEEDS_DIR / self.db_type

        if not seed_dir.exists():
            print(f"[migrate] Warning: Seed directory not found: {seed_dir}")
            return seeds

        for f in sorted(seed_dir.glob('*.sql')):
            version = f.stem.split('_')[0]
            seeds.append((version, f))

        return seeds

    def calculate_checksum(self, filepath: Path) -> str:
        """Calculate MD5 checksum of a file."""
        return hashlib.md5(filepath.read_bytes()).hexdigest()

    def run_sql_file(self, filepath: Path) -> int:
        """
        Execute SQL file and return execution time in ms.
        Handles multiple statements separated by semicolons.
        """
        start = datetime.now()

        sql_content = filepath.read_text(encoding='utf-8')

        # Split by semicolons but handle edge cases
        # For MySQL, we need to handle DELIMITER changes for triggers/procedures
        statements = self._split_sql_statements(sql_content)

        for stmt in statements:
            stmt = stmt.strip()
            if stmt and not stmt.startswith('--'):
                try:
                    self.cursor.execute(stmt)
                except Exception as e:
                    # Some statements might fail if objects already exist
                    # Log but continue for IF NOT EXISTS type statements
                    if 'already exists' in str(e).lower() or 'duplicate' in str(e).lower():
                        print(f"[migrate] Note: {e}")
                    else:
                        raise

        self.conn.commit()

        elapsed = (datetime.now() - start).total_seconds() * 1000
        return int(elapsed)

    def _split_sql_statements(self, sql: str) -> List[str]:
        """
        Split SQL content into individual statements.
        Handles MySQL DELIMITER changes and PostgreSQL DO blocks.
        Properly handles parentheses and quoted strings.
        """
        statements = []
        current = []
        delimiter = ';'
        in_block = False
        paren_depth = 0
        in_string = False
        string_char = None

        for line in sql.split('\n'):
            stripped = line.strip().upper()

            # Handle DELIMITER change (MySQL)
            if stripped.startswith('DELIMITER'):
                parts = line.strip().split()
                if len(parts) >= 2:
                    delimiter = parts[1]
                continue

            # Handle PostgreSQL DO blocks
            if '$$' in line:
                in_block = not in_block

            current.append(line)

            # Track parenthesis depth for proper statement splitting
            for i, char in enumerate(line):
                # Track string literals
                if char in ('"', "'") and (i == 0 or line[i-1] != '\\'):
                    if not in_string:
                        in_string = True
                        string_char = char
                    elif char == string_char:
                        in_string = False
                        string_char = None

                if not in_string:
                    if char == '(':
                        paren_depth += 1
                    elif char == ')':
                        paren_depth -= 1

            # Check for statement end - only when not inside parentheses or blocks
            if not in_block and paren_depth == 0 and line.rstrip().endswith(delimiter):
                stmt = '\n'.join(current)
                if delimiter != ';':
                    stmt = stmt.rstrip(delimiter)
                stmt = stmt.strip()

                # Remove leading comment lines and check if there's actual SQL
                lines_without_comments = [l for l in stmt.split('\n') if l.strip() and not l.strip().startswith('--')]
                if lines_without_comments:
                    statements.append(stmt)

                current = []
                paren_depth = 0

        # Add any remaining content
        if current:
            stmt = '\n'.join(current).strip()
            lines_without_comments = [l for l in stmt.split('\n') if l.strip() and not l.strip().startswith('--')]
            if lines_without_comments:
                statements.append(stmt)

        return statements

    def run_migrations(self, force: bool = False) -> int:
        """
        Run all pending migrations.
        Returns number of migrations applied.
        """
        self.ensure_migrations_table()

        applied = set(self.get_applied_migrations())
        migrations = self.get_migration_files()
        count = 0

        for version, filepath in migrations:
            if version in applied and not force:
                print(f"[migrate] Skipping {filepath.name} (already applied)")
                continue

            print(f"[migrate] Running migration: {filepath.name}")

            try:
                checksum = self.calculate_checksum(filepath)
                exec_time = self.run_sql_file(filepath)

                # Record migration
                if self.db_type == 'postgresql':
                    self.cursor.execute("""
                        INSERT INTO _migrations (version, name, checksum, execution_time_ms)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (version) DO UPDATE SET
                            applied_at = CURRENT_TIMESTAMP,
                            checksum = EXCLUDED.checksum,
                            execution_time_ms = EXCLUDED.execution_time_ms
                    """, (version, filepath.name, checksum, exec_time))
                else:  # mysql
                    self.cursor.execute("""
                        INSERT INTO _migrations (version, name, checksum, execution_time_ms)
                        VALUES (%s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            applied_at = CURRENT_TIMESTAMP,
                            checksum = VALUES(checksum),
                            execution_time_ms = VALUES(execution_time_ms)
                    """, (version, filepath.name, checksum, exec_time))

                self.conn.commit()
                print(f"[migrate] ✓ Applied {filepath.name} ({exec_time}ms)")
                count += 1

            except Exception as e:
                self.conn.rollback()
                print(f"[migrate] ✗ Failed {filepath.name}: {e}")
                raise

        return count

    def run_seeds(self) -> int:
        """
        Run all seed files.
        Returns number of seeds applied.
        """
        seeds = self.get_seed_files()
        count = 0

        for version, filepath in seeds:
            print(f"[migrate] Running seed: {filepath.name}")

            try:
                exec_time = self.run_sql_file(filepath)
                print(f"[migrate] ✓ Seeded {filepath.name} ({exec_time}ms)")
                count += 1
            except Exception as e:
                self.conn.rollback()
                print(f"[migrate] ✗ Seed failed {filepath.name}: {e}")
                raise

        return count

    def show_status(self):
        """Display migration status."""
        self.ensure_migrations_table()

        applied = self.get_applied_migrations()
        migrations = self.get_migration_files()

        print(f"\n{'='*60}")
        print(f"Migration Status ({self.db_type.upper()})")
        print(f"{'='*60}")

        for version, filepath in migrations:
            status = "✓ Applied" if version in applied else "○ Pending"
            print(f"  {version}: {filepath.name} [{status}]")

        print(f"\nTotal: {len(migrations)} migrations, {len(applied)} applied")
        print(f"{'='*60}\n")

    def reset(self):
        """
        Reset all migrations (DANGEROUS - drops tracking table).
        Use with caution!
        """
        print("[migrate] WARNING: Resetting migration history!")
        self.cursor.execute("DROP TABLE IF EXISTS _migrations")
        self.conn.commit()
        print("[migrate] Migration history cleared")


def wait_for_database(max_retries: int = 30, delay: int = 2):
    """Wait for database to be available."""
    import time

    config = get_db_config()

    for i in range(max_retries):
        try:
            if DB_TYPE == 'postgresql':
                import psycopg2
                conn = psycopg2.connect(**config)
            else:
                import pymysql
                conn = pymysql.connect(**config)
            conn.close()
            print(f"[migrate] Database is ready")
            return True
        except Exception as e:
            print(f"[migrate] Waiting for database... ({i+1}/{max_retries})")
            time.sleep(delay)

    print("[migrate] Database connection failed after max retries")
    return False


def main():
    parser = argparse.ArgumentParser(
        description='Database Migration System',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--status', action='store_true',
                        help='Show migration status')
    parser.add_argument('--seed', action='store_true',
                        help='Run seed data')
    parser.add_argument('--reset', action='store_true',
                        help='Reset migration history (DANGEROUS!)')
    parser.add_argument('--force', action='store_true',
                        help='Force re-run all migrations')
    parser.add_argument('--wait', action='store_true',
                        help='Wait for database to be available')

    args = parser.parse_args()

    print(f"[migrate] Database type: {DB_TYPE}")
    print(f"[migrate] Migrations dir: {MigrationRunner.MIGRATIONS_DIR}")

    # Wait for database if requested
    if args.wait:
        if not wait_for_database():
            sys.exit(1)

    runner = MigrationRunner()

    try:
        runner.connect()

        if args.status:
            runner.show_status()
        elif args.reset:
            confirm = input("Are you sure you want to reset? Type 'yes' to confirm: ")
            if confirm.lower() == 'yes':
                runner.reset()
                runner.run_migrations(force=True)
            else:
                print("Reset cancelled")
        elif args.seed:
            count = runner.run_seeds()
            print(f"[migrate] Completed: {count} seeds applied")
        else:
            count = runner.run_migrations(force=args.force)
            print(f"[migrate] Completed: {count} migrations applied")

    except Exception as e:
        print(f"[migrate] Error: {e}")
        sys.exit(1)
    finally:
        runner.close()


if __name__ == '__main__':
    main()
