#!/usr/bin/env python3
"""
TMT (Thai Medicines Terminology) Importer

Import TMT data from NHSO TMT Release files into the database.
Supports:
- FULL import (complete replacement)
- DELTA import (incremental updates)
- SNAPSHOT import (active drugs only)

TMT File Types:
- TMTRF*_FULL.xls: Complete list including invalid items (35,000+ records)
- TMTRF*_SNAPSHOT.xls: Active items only
- TMTRF*_DELTA.xls: Changes since last release
- TMTRF*_SNAPSHOT_GP_F.xls: Generic Products

Source: http://tmt.this.or.th/
"""

import os
import re
import sys
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple
import pandas as pd

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)


def parse_fsn(fsn: str) -> Dict[str, Optional[str]]:
    """
    Parse FSN (Full Specified Name) to extract drug information.

    FSN Format examples:
    - "VIVACOR (10MG) (IPR PHARMACEUTICALS) (rosuvastatin 10 mg) film-coated tablet, 1 tablet (TPU)"
    - "0.0001% DPCP (F 12249) (diphenylcyclopropenone 100 mcg/100 mL) cutaneous solution, 5 mL bottle (TPU)"

    Args:
        fsn: Full Specified Name string

    Returns:
        Dict with trade_name, generic_name, strength, dosage_form, unit, package_size
    """
    result = {
        'trade_name': None,
        'generic_name': None,
        'strength': None,
        'dosage_form': None,
        'unit': None,
        'package_size': None,
        'package_unit': None
    }

    if pd.isna(fsn) or not fsn:
        return result

    fsn = str(fsn).strip()

    # Extract generic name and strength from parentheses
    # Pattern: (generic_name strength) e.g., (rosuvastatin 10 mg)
    generic_match = re.search(r'\(([a-zA-Z][a-zA-Z\s\-\+]+?)\s+([\d\.]+\s*\w+(?:/[\d\.]+\s*\w+)?)\)', fsn)
    if generic_match:
        result['generic_name'] = generic_match.group(1).strip()
        result['strength'] = generic_match.group(2).strip()

    # Extract trade name (before first parenthesis, uppercase letters)
    trade_match = re.match(r'^([A-Z][A-Z0-9\s\-\.%]+?)(?:\s*\(|$)', fsn)
    if trade_match:
        trade = trade_match.group(1).strip()
        # Exclude if it's a percentage or code
        if trade and not trade[0].isdigit():
            result['trade_name'] = trade.rstrip('.')

    # Extract dosage form (after last strength parenthesis, before package info)
    # e.g., "film-coated tablet", "cutaneous solution"
    form_match = re.search(r'\)\s*([a-zA-Z][a-zA-Z\s\-]+?)(?:,\s*\d|\s*\((?:TPU|GPU|GPUID|VTM))', fsn)
    if form_match:
        form = form_match.group(1).strip()
        # Clean up common suffixes
        form = re.sub(r'\s*,?\s*$', '', form)
        result['dosage_form'] = form

    # Extract package size and unit (e.g., "1 tablet", "60 mL bottle", "5 mL")
    package_match = re.search(r',\s*([\d\.]+)\s*([a-zA-Z]+(?:\s+[a-zA-Z]+)?)\s*\((?:TPU|GPU)', fsn)
    if package_match:
        result['package_size'] = package_match.group(1)
        result['package_unit'] = package_match.group(2).strip()

    return result


def parse_tmt_date(date_val) -> Optional[datetime]:
    """
    Parse TMT date format (YYYYMMDD as integer or string).

    Args:
        date_val: Date value from Excel (int like 20251201)

    Returns:
        datetime object or None
    """
    if pd.isna(date_val):
        return None

    try:
        date_str = str(int(date_val))
        if len(date_str) == 8:
            return datetime.strptime(date_str, '%Y%m%d')
    except (ValueError, TypeError):
        pass

    return None


class TMTImporter:
    """
    TMT Database Importer
    """

    def __init__(self, db_config: Dict, db_type: str = 'postgresql'):
        """
        Initialize TMT Importer.

        Args:
            db_config: Database connection config
            db_type: 'postgresql' or 'mysql'
        """
        self.db_config = db_config
        self.db_type = db_type
        self.conn = None
        self.cursor = None

    def connect(self):
        """Establish database connection"""
        if self.db_type == 'postgresql':
            import psycopg2
            self.conn = psycopg2.connect(**self.db_config)
            self.cursor = self.conn.cursor()
        elif self.db_type == 'mysql':
            import pymysql
            self.conn = pymysql.connect(**self.db_config)
            self.cursor = self.conn.cursor()
        logger.info(f"Database connection established ({self.db_type})")

    def disconnect(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        logger.info("Database connection closed")

    def import_full(self, filepath: str, clear_existing: bool = True) -> Dict:
        """
        Import TMT FULL file (complete replacement).

        Args:
            filepath: Path to TMTRF*_FULL.xls file
            clear_existing: Whether to delete existing data first

        Returns:
            Dict with import results
        """
        logger.info(f"Importing TMT FULL from: {filepath}")

        # Read Excel file
        df = pd.read_excel(filepath, engine='xlrd')
        total_records = len(df)
        logger.info(f"Found {total_records:,} records in file")

        # Clear existing data if requested
        if clear_existing:
            self.cursor.execute("DELETE FROM tmt_drugs")
            self.conn.commit()
            logger.info("Cleared existing TMT data")

        # Process and import
        imported = 0
        errors = 0

        for idx, row in df.iterrows():
            try:
                tmt_code = str(row.get('TMTID(TPU)', row.get('TMTID(TPUID)', ''))).strip()
                if not tmt_code:
                    continue

                fsn = row.get('FSN', '')
                parsed = parse_fsn(fsn)

                manufacturer = row.get('MANUFACTURER', '')
                change_date = parse_tmt_date(row.get('CHANGEDATE'))
                issue_date = parse_tmt_date(row.get('ISSUEDATE'))
                effective_date = parse_tmt_date(row.get('EFFECTIVEDATE'))
                invalid_date = parse_tmt_date(row.get('INVALIDDATE'))
                is_invalid = bool(row.get('INVALID', 0))

                # Insert or update
                if self.db_type == 'postgresql':
                    query = """
                        INSERT INTO tmt_drugs (
                            tmt_code, fsn, generic_name, trade_name, strength,
                            dosage_form, package_size, package_unit, manufacturer,
                            change_date, issue_date, effective_date, invalid_date,
                            is_active
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (tmt_code) DO UPDATE SET
                            fsn = EXCLUDED.fsn,
                            generic_name = EXCLUDED.generic_name,
                            trade_name = EXCLUDED.trade_name,
                            strength = EXCLUDED.strength,
                            dosage_form = EXCLUDED.dosage_form,
                            package_size = EXCLUDED.package_size,
                            package_unit = EXCLUDED.package_unit,
                            manufacturer = EXCLUDED.manufacturer,
                            change_date = EXCLUDED.change_date,
                            issue_date = EXCLUDED.issue_date,
                            effective_date = EXCLUDED.effective_date,
                            invalid_date = EXCLUDED.invalid_date,
                            is_active = EXCLUDED.is_active,
                            updated_at = CURRENT_TIMESTAMP
                    """
                else:  # mysql
                    query = """
                        INSERT INTO tmt_drugs (
                            tmt_code, fsn, generic_name, trade_name, strength,
                            dosage_form, package_size, package_unit, manufacturer,
                            change_date, issue_date, effective_date, invalid_date,
                            is_active
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            fsn = VALUES(fsn),
                            generic_name = VALUES(generic_name),
                            trade_name = VALUES(trade_name),
                            strength = VALUES(strength),
                            dosage_form = VALUES(dosage_form),
                            package_size = VALUES(package_size),
                            package_unit = VALUES(package_unit),
                            manufacturer = VALUES(manufacturer),
                            change_date = VALUES(change_date),
                            issue_date = VALUES(issue_date),
                            effective_date = VALUES(effective_date),
                            invalid_date = VALUES(invalid_date),
                            is_active = VALUES(is_active),
                            updated_at = CURRENT_TIMESTAMP
                    """

                values = (
                    tmt_code[:50],  # tmt_code max length
                    fsn[:1000] if fsn else None,  # fsn
                    parsed['generic_name'][:200] if parsed['generic_name'] else None,
                    parsed['trade_name'][:200] if parsed['trade_name'] else None,
                    parsed['strength'][:100] if parsed['strength'] else None,
                    parsed['dosage_form'][:100] if parsed['dosage_form'] else None,
                    parsed['package_size'][:50] if parsed['package_size'] else None,
                    parsed['package_unit'][:50] if parsed['package_unit'] else None,
                    str(manufacturer)[:200] if manufacturer else None,
                    change_date,
                    issue_date,
                    effective_date,
                    invalid_date,
                    not is_invalid  # is_active = NOT invalid
                )

                self.cursor.execute(query, values)
                imported += 1

                # Commit every 1000 records
                if imported % 1000 == 0:
                    self.conn.commit()
                    logger.info(f"Imported {imported:,}/{total_records:,} records...")

            except Exception as e:
                errors += 1
                if errors <= 5:
                    logger.warning(f"Error importing row {idx}: {e}")

        self.conn.commit()

        result = {
            'success': True,
            'total_records': total_records,
            'imported': imported,
            'errors': errors
        }
        logger.info(f"TMT FULL import complete: {imported:,} imported, {errors} errors")
        return result

    def import_delta(self, filepath: str) -> Dict:
        """
        Import TMT DELTA file (incremental updates only).

        Args:
            filepath: Path to TMTRF*_DELTA.xls file

        Returns:
            Dict with import results
        """
        logger.info(f"Importing TMT DELTA from: {filepath}")

        # Read Excel file
        df = pd.read_excel(filepath, engine='xlrd')
        total_records = len(df)
        logger.info(f"Found {total_records:,} delta records")

        updated = 0
        inserted = 0
        errors = 0

        for idx, row in df.iterrows():
            try:
                tmt_code = str(row.get('TMTID(TPU)', row.get('TMTID(TPUID)', ''))).strip()
                if not tmt_code:
                    continue

                fsn = row.get('FSN', '')
                parsed = parse_fsn(fsn)
                manufacturer = row.get('MANUFACTURER', '')
                change_date = parse_tmt_date(row.get('CHANGEDATE'))

                # Check if exists
                self.cursor.execute(
                    "SELECT id FROM tmt_drugs WHERE tmt_code = %s",
                    (tmt_code,)
                )
                exists = self.cursor.fetchone()

                if exists:
                    # Update existing
                    query = """
                        UPDATE tmt_drugs SET
                            fsn = %s,
                            generic_name = %s,
                            trade_name = %s,
                            strength = %s,
                            dosage_form = %s,
                            manufacturer = %s,
                            change_date = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE tmt_code = %s
                    """
                    values = (
                        fsn[:1000] if fsn else None,
                        parsed['generic_name'][:200] if parsed['generic_name'] else None,
                        parsed['trade_name'][:200] if parsed['trade_name'] else None,
                        parsed['strength'][:100] if parsed['strength'] else None,
                        parsed['dosage_form'][:100] if parsed['dosage_form'] else None,
                        str(manufacturer)[:200] if manufacturer else None,
                        change_date,
                        tmt_code
                    )
                    self.cursor.execute(query, values)
                    updated += 1
                else:
                    # Insert new
                    query = """
                        INSERT INTO tmt_drugs (
                            tmt_code, fsn, generic_name, trade_name, strength,
                            dosage_form, manufacturer, change_date, is_active
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    values = (
                        tmt_code[:50],
                        fsn[:1000] if fsn else None,
                        parsed['generic_name'][:200] if parsed['generic_name'] else None,
                        parsed['trade_name'][:200] if parsed['trade_name'] else None,
                        parsed['strength'][:100] if parsed['strength'] else None,
                        parsed['dosage_form'][:100] if parsed['dosage_form'] else None,
                        str(manufacturer)[:200] if manufacturer else None,
                        change_date,
                        True
                    )
                    self.cursor.execute(query, values)
                    inserted += 1

            except Exception as e:
                errors += 1
                if errors <= 5:
                    logger.warning(f"Error importing delta row {idx}: {e}")

        self.conn.commit()

        result = {
            'success': True,
            'total_records': total_records,
            'updated': updated,
            'inserted': inserted,
            'errors': errors
        }
        logger.info(f"TMT DELTA import complete: {updated} updated, {inserted} inserted, {errors} errors")
        return result

    def get_stats(self) -> Dict:
        """Get TMT database statistics."""
        self.cursor.execute("SELECT COUNT(*) FROM tmt_drugs")
        total = self.cursor.fetchone()[0]

        self.cursor.execute("SELECT COUNT(*) FROM tmt_drugs WHERE is_active = true")
        active = self.cursor.fetchone()[0]

        self.cursor.execute("SELECT MAX(change_date) FROM tmt_drugs")
        last_update = self.cursor.fetchone()[0]

        return {
            'total_drugs': total,
            'active_drugs': active,
            'inactive_drugs': total - active,
            'last_update': last_update
        }

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


def import_tmt_full(filepath: str, db_config: Dict, db_type: str = 'postgresql') -> Dict:
    """
    Convenience function to import TMT FULL file.

    Args:
        filepath: Path to TMTRF*_FULL.xls file
        db_config: Database configuration
        db_type: 'postgresql' or 'mysql'

    Returns:
        Import result dict
    """
    with TMTImporter(db_config, db_type) as importer:
        result = importer.import_full(filepath)
        stats = importer.get_stats()
        result['stats'] = stats
    return result


def import_tmt_delta(filepath: str, db_config: Dict, db_type: str = 'postgresql') -> Dict:
    """
    Convenience function to import TMT DELTA file.

    Args:
        filepath: Path to TMTRF*_DELTA.xls file
        db_config: Database configuration
        db_type: 'postgresql' or 'mysql'

    Returns:
        Import result dict
    """
    with TMTImporter(db_config, db_type) as importer:
        result = importer.import_delta(filepath)
        stats = importer.get_stats()
        result['stats'] = stats
    return result


if __name__ == '__main__':
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    parser = argparse.ArgumentParser(description='Import TMT data')
    parser.add_argument('filepath', help='Path to TMT Excel file')
    parser.add_argument('--type', choices=['full', 'delta', 'snapshot'], default='full',
                        help='Import type (default: full)')
    args = parser.parse_args()

    from config.database import get_db_config, DB_TYPE

    db_config = get_db_config()

    if args.type == 'full':
        result = import_tmt_full(args.filepath, db_config, DB_TYPE)
    elif args.type == 'delta':
        result = import_tmt_delta(args.filepath, db_config, DB_TYPE)
    else:
        print(f"Import type '{args.type}' not implemented yet")
        sys.exit(1)

    print("\n=== Import Result ===")
    for key, value in result.items():
        print(f"{key}: {value}")
