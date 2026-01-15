#!/usr/bin/env python3
"""
Master Data Importer

Import master data tables:
- ICD-10-TM (Thai Modification) diagnosis codes
- ICD-9-CM procedure codes
- DRG codes (Thai DRG)
"""

import os
import sys
import re
import logging
from typing import Dict, Optional
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)


class MasterDataImporter:
    """
    Import master data into database
    """

    def __init__(self, db_config: Dict, db_type: str = 'postgresql'):
        self.db_config = db_config
        self.db_type = db_type
        self.conn = None
        self.cursor = None

    def connect(self):
        if self.db_type == 'postgresql':
            import psycopg2
            self.conn = psycopg2.connect(**self.db_config)
            self.cursor = self.conn.cursor()
        elif self.db_type == 'mysql':
            import pymysql
            self.conn = pymysql.connect(**self.db_config)
            self.cursor = self.conn.cursor()
        logger.info(f"Database connected ({self.db_type})")

    def disconnect(self):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        logger.info("Database disconnected")

    def import_icd10_tm(self, filepath: str, clear_existing: bool = True) -> Dict:
        """
        Import ICD-10-TM from Excel file.

        Expected columns: Code, CodePlain, Level, Term, ICD-10-TM, CHAPTER, BLOCK, GROUP

        Args:
            filepath: Path to ICD10TM-Public.xlsx
            clear_existing: Clear existing data first

        Returns:
            Import result dict
        """
        logger.info(f"Importing ICD-10-TM from: {filepath}")

        # Read Data sheet
        df = pd.read_excel(filepath, sheet_name='Data')
        total = len(df)
        logger.info(f"Found {total:,} ICD-10-TM records")

        if clear_existing:
            self.cursor.execute("DELETE FROM icd10_codes")
            self.conn.commit()
            logger.info("Cleared existing ICD-10 data")

        imported = 0
        errors = 0

        for idx, row in df.iterrows():
            try:
                code = str(row.get('Code', '')).strip()
                if not code:
                    continue

                # Skip header rows (Level 1 with ICD-10-TM = 'HEADING')
                icd_tm = row.get('ICD-10-TM', '')
                if icd_tm == 'HEADING':
                    continue

                term = str(row.get('Term', '')).strip()
                chapter = str(row.get('CHAPTER', '')).strip() if pd.notna(row.get('CHAPTER')) else None
                block = str(row.get('BLOCK', '')).strip() if pd.notna(row.get('BLOCK')) else None
                group = str(row.get('GROUP', '')).strip() if pd.notna(row.get('GROUP')) else None
                level = int(row.get('Level', 0)) if pd.notna(row.get('Level')) else None

                if self.db_type == 'postgresql':
                    query = """
                        INSERT INTO icd10_codes (code, description_en, chapter, block_name, level)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (code) DO UPDATE SET
                            description_en = EXCLUDED.description_en,
                            chapter = EXCLUDED.chapter,
                            block_name = EXCLUDED.block_name,
                            level = EXCLUDED.level,
                            updated_at = CURRENT_TIMESTAMP
                    """
                else:
                    query = """
                        INSERT INTO icd10_codes (code, description_en, chapter, block_name, level)
                        VALUES (%s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            description_en = VALUES(description_en),
                            chapter = VALUES(chapter),
                            block_name = VALUES(block_name),
                            level = VALUES(level),
                            updated_at = CURRENT_TIMESTAMP
                    """

                values = (
                    code[:10],
                    term[:500] if term else None,
                    chapter[:100] if chapter else None,
                    block[:100] if block else None,
                    level
                )

                self.cursor.execute(query, values)
                imported += 1

                if imported % 5000 == 0:
                    self.conn.commit()
                    logger.info(f"Imported {imported:,}/{total:,} records...")

            except Exception as e:
                errors += 1
                if errors <= 5:
                    logger.warning(f"Error importing row {idx}: {e}")

        self.conn.commit()

        result = {
            'success': True,
            'total_records': total,
            'imported': imported,
            'errors': errors
        }
        logger.info(f"ICD-10-TM import complete: {imported:,} imported, {errors} errors")
        return result

    def import_icd9cm_procedures(self, filepath: str, clear_existing: bool = True) -> Dict:
        """
        Import ICD-9-CM procedure codes from text file.

        Expected format: CODE<space>DESCRIPTION (one per line)
        Example: 0001 Therapeutic ultrasound of vessels of head and neck

        Args:
            filepath: Path to CMS32_DESC_LONG_SG.txt
            clear_existing: Clear existing data first

        Returns:
            Import result dict
        """
        logger.info(f"Importing ICD-9-CM procedures from: {filepath}")

        # Read text file
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        total = len(lines)
        logger.info(f"Found {total:,} ICD-9-CM procedure records")

        if clear_existing:
            self.cursor.execute("DELETE FROM icd9cm_procedures")
            self.conn.commit()
            logger.info("Cleared existing ICD-9-CM data")

        imported = 0
        errors = 0

        for line in lines:
            try:
                line = line.strip()
                if not line:
                    continue

                # Format: CODE (4 chars) + space + description
                # Code can be like: 0001, 01.2, 99.99
                match = re.match(r'^(\d{2,4}\.?\d*)\s+(.+)$', line)
                if not match:
                    continue

                code = match.group(1).strip()
                description = match.group(2).strip()

                # Format code with decimal if needed
                if len(code) == 4 and '.' not in code:
                    code = code[:2] + '.' + code[2:]
                elif len(code) == 3 and '.' not in code:
                    code = code[:2] + '.' + code[2:]

                if self.db_type == 'postgresql':
                    query = """
                        INSERT INTO icd9cm_procedures (code, description_en)
                        VALUES (%s, %s)
                        ON CONFLICT (code) DO UPDATE SET
                            description_en = EXCLUDED.description_en,
                            updated_at = CURRENT_TIMESTAMP
                    """
                else:
                    query = """
                        INSERT INTO icd9cm_procedures (code, description_en)
                        VALUES (%s, %s)
                        ON DUPLICATE KEY UPDATE
                            description_en = VALUES(description_en),
                            updated_at = CURRENT_TIMESTAMP
                    """

                values = (code[:10], description[:500] if description else None)
                self.cursor.execute(query, values)
                imported += 1

                if imported % 1000 == 0:
                    self.conn.commit()
                    logger.info(f"Imported {imported:,}/{total:,} records...")

            except Exception as e:
                errors += 1
                if errors <= 5:
                    logger.warning(f"Error importing line: {e}")

        self.conn.commit()

        result = {
            'success': True,
            'total_records': total,
            'imported': imported,
            'errors': errors
        }
        logger.info(f"ICD-9-CM procedures import complete: {imported:,} imported, {errors} errors")
        return result

    def get_stats(self) -> Dict:
        """Get master data statistics"""
        stats = {}

        tables = ['icd10_codes', 'icd9cm_procedures', 'drg_codes',
                  'nhso_error_codes', 'fund_types', 'service_types',
                  'tmt_drugs', 'dim_date']

        for table in tables:
            try:
                self.cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[table] = self.cursor.fetchone()[0]
            except Exception:
                stats[table] = 0

        return stats

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


def import_all_masterdata(db_config: Dict, db_type: str = 'postgresql') -> Dict:
    """
    Import all available master data files.

    Args:
        db_config: Database configuration
        db_type: Database type

    Returns:
        Combined results dict
    """
    downloads_dir = '/Users/sathitseethaphon/Downloads'
    results = {}

    with MasterDataImporter(db_config, db_type) as importer:
        # ICD-10-TM
        icd10_file = os.path.join(downloads_dir, 'ICD10TM-Public.xlsx')
        if os.path.exists(icd10_file):
            results['icd10'] = importer.import_icd10_tm(icd10_file)
        else:
            logger.warning(f"ICD-10-TM file not found: {icd10_file}")

        # ICD-9-CM Procedures
        icd9_file = os.path.join(downloads_dir, 'icd9cm_procedures.txt')
        if os.path.exists(icd9_file):
            results['icd9cm'] = importer.import_icd9cm_procedures(icd9_file)
        else:
            logger.warning(f"ICD-9-CM file not found: {icd9_file}")

        # Get final stats
        results['stats'] = importer.get_stats()

    return results


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    from config.database import get_db_config, DB_TYPE

    results = import_all_masterdata(get_db_config(), DB_TYPE)

    print("\n=== Master Data Import Results ===")
    for key, value in results.items():
        print(f"{key}: {value}")
