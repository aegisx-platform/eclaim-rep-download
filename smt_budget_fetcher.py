#!/usr/bin/env python3
"""
SMT Budget Report Fetcher
Fetches payment/reimbursement data from NHSO Smart Money Transfer (SMT) system.

API: https://smt.nhso.go.th/smtf/api/budgetreport/budgetSummaryByVendorReport/search

Usage:
    python smt_budget_fetcher.py                              # Current fiscal year
    python smt_budget_fetcher.py --vendor-id 10670            # Specific vendor
    python smt_budget_fetcher.py --start-date 01/10/2568 --end-date 10/01/2569
    python smt_budget_fetcher.py --export json                # Export to JSON
    python smt_budget_fetcher.py --export csv                 # Export to CSV
    python smt_budget_fetcher.py --save-db                    # Save to database
"""

import os
import sys
import json
import csv
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class SMTBudgetFetcher:
    """
    Fetches budget/payment data from NHSO Smart Money Transfer (SMT) system.

    The SMT API is publicly accessible without authentication.
    """

    BASE_URL = 'https://smt.nhso.go.th/smtf/api'
    BUDGET_SUMMARY_ENDPOINT = '/budgetreport/budgetSummaryByVendorReport/search'

    # Zone mappings (เขต)
    ZONES = {
        '01': 'เขต 1 เชียงใหม่',
        '02': 'เขต 2 พิษณุโลก',
        '03': 'เขต 3 นครสวรรค์',
        '04': 'เขต 4 สระบุรี',
        '05': 'เขต 5 ราชบุรี',
        '06': 'เขต 6 ระยอง',
        '07': 'เขต 7 ขอนแก่น',
        '08': 'เขต 8 อุดรธานี',
        '09': 'เขต 9 นครราชสีมา',
        '10': 'เขต 10 อุบลราชธานี',
        '11': 'เขต 11 สุราษฎร์ธานี',
        '12': 'เขต 12 สงขลา',
        '13': 'เขต 13 กรุงเทพมหานคร',
    }

    def __init__(self, vendor_id: str = None, zone_id: str = None, province_id: str = None):
        """
        Initialize SMT Budget Fetcher.

        Args:
            vendor_id: 5 or 10-digit vendor/hospital ID
            zone_id: Zone ID (01-13)
            province_id: Province ID (e.g., 4000 for Khon Kaen)
        """
        self.vendor_id = self._format_vendor_id(vendor_id) if vendor_id else None
        self.zone_id = zone_id or ''
        self.province_id = province_id or ''

        # Create session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'th,en-US;q=0.9,en;q=0.8',
            'Content-Type': 'application/json',
            'Origin': 'https://smt.nhso.go.th',
            'Referer': 'https://smt.nhso.go.th/smtf/',
        })

        # Output directory - use downloads/smt for consistency
        self.output_dir = Path('downloads/smt')
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _format_vendor_id(self, vendor_id: str) -> str:
        """Format vendor ID to 10-digit format."""
        vendor_id = str(vendor_id).strip()
        if len(vendor_id) == 5:
            return f"00000{vendor_id}"
        elif len(vendor_id) == 10:
            return vendor_id
        else:
            # Pad to 10 digits
            return vendor_id.zfill(10)

    def _get_current_fiscal_year_dates(self) -> tuple:
        """
        Get current Thai fiscal year date range.
        Thai fiscal year: October 1 - September 30

        Returns:
            (start_date, end_date) in dd/mm/yyyy Buddhist Era format
        """
        now = datetime.now()
        be_year = now.year + 543  # Convert to Buddhist Era

        # Determine fiscal year
        if now.month >= 10:
            # Current fiscal year started this October
            fiscal_year = be_year + 1
            start_year = be_year
        else:
            # Current fiscal year started last October
            fiscal_year = be_year
            start_year = be_year - 1

        start_date = f"01/10/{start_year}"
        end_date = now.strftime(f"%d/%m/{be_year}")

        return start_date, end_date, fiscal_year

    def fetch_budget_summary(
        self,
        budget_year: int = None,
        start_date: str = None,
        end_date: str = None,
        budget_source: str = '',
        vendor_search_condition: str = '1'
    ) -> Dict[str, Any]:
        """
        Fetch budget summary report from SMT API.

        Args:
            budget_year: Budget year in Buddhist Era (e.g., 2569)
            start_date: Start date in dd/mm/yyyy BE format (e.g., 01/10/2568)
            end_date: End date in dd/mm/yyyy BE format (e.g., 10/01/2569)
            budget_source: Budget source filter ('UC', '', etc.)
            vendor_search_condition: Search condition code ('1' = by vendor ID)

        Returns:
            API response dict with 'datas' array
        """
        # Get default dates if not provided
        if not start_date or not end_date:
            start_date, end_date, fiscal_year = self._get_current_fiscal_year_dates()
            if not budget_year:
                budget_year = fiscal_year

        if not budget_year:
            budget_year = datetime.now().year + 543 + (1 if datetime.now().month >= 10 else 0)

        # Build request payload
        payload = {
            'vendorSearchConditionCode': vendor_search_condition,
            'zoneId': self.zone_id,
            'provinceId': self.province_id,
            'vendorId': self.vendor_id or '',
            'vendorId5Digit': '',
            'budgetSource': budget_source,
            'budgetYear': str(budget_year),
            'transferStartDate': start_date,
            'transferEndDate': end_date,
            'hospType': None,
            'isTest': ''
        }

        url = f"{self.BASE_URL}{self.BUDGET_SUMMARY_ENDPOINT}"

        print(f"Fetching budget data from SMT API...")
        print(f"  URL: {url}")
        print(f"  Vendor ID: {self.vendor_id or 'All'}")
        print(f"  Date Range: {start_date} - {end_date}")
        print(f"  Budget Year: {budget_year}")

        try:
            response = self.session.post(url, json=payload, timeout=60)
            response.raise_for_status()

            data = response.json()
            records = data.get('datas', [])

            print(f"  Found {len(records)} records")

            return data

        except requests.exceptions.RequestException as e:
            print(f"Error fetching data: {e}")
            return {'datas': [], 'error': str(e)}

    def calculate_summary(self, records: List[Dict]) -> Dict[str, Any]:
        """
        Calculate summary statistics from records.

        Args:
            records: List of payment records

        Returns:
            Summary dict with totals by fund type
        """
        summary = {
            'total_records': len(records),
            'total_amount': 0,
            'total_by_fund': {},
            'total_by_fund_group': {},
            'records_by_month': {},
        }

        for record in records:
            amount = record.get('amount', 0) or 0
            fund_name = record.get('fundName', 'Unknown')
            fund_group = record.get('fundGroupDescr', 'Unknown')
            posting_date = record.get('postingDate', '')

            # Total amount
            summary['total_amount'] += amount

            # By fund name
            if fund_name not in summary['total_by_fund']:
                summary['total_by_fund'][fund_name] = {'amount': 0, 'count': 0}
            summary['total_by_fund'][fund_name]['amount'] += amount
            summary['total_by_fund'][fund_name]['count'] += 1

            # By fund group
            if fund_group not in summary['total_by_fund_group']:
                summary['total_by_fund_group'][fund_group] = {'amount': 0, 'count': 0}
            summary['total_by_fund_group'][fund_group]['amount'] += amount
            summary['total_by_fund_group'][fund_group]['count'] += 1

            # By month (extract from postingDate: YYYYMMDD)
            if posting_date and len(posting_date) >= 6:
                month_key = posting_date[:6]  # YYYYMM
                if month_key not in summary['records_by_month']:
                    summary['records_by_month'][month_key] = {'amount': 0, 'count': 0}
                summary['records_by_month'][month_key]['amount'] += amount
                summary['records_by_month'][month_key]['count'] += 1

        return summary

    def print_summary(self, summary: Dict[str, Any]):
        """Print formatted summary to console."""
        print("\n" + "=" * 60)
        print("BUDGET SUMMARY REPORT")
        print("=" * 60)

        print(f"\nTotal Records: {summary['total_records']}")
        print(f"Total Amount:  {summary['total_amount']:,.2f} Baht")

        if summary['total_by_fund_group']:
            print("\n--- By Fund Group ---")
            for fund_group, data in sorted(summary['total_by_fund_group'].items()):
                print(f"  {fund_group}: {data['amount']:,.2f} Baht ({data['count']} records)")

        if summary['total_by_fund']:
            print("\n--- By Fund ---")
            for fund, data in sorted(summary['total_by_fund'].items()):
                print(f"  {fund}: {data['amount']:,.2f} Baht ({data['count']} records)")

        if summary['records_by_month']:
            print("\n--- By Month ---")
            for month, data in sorted(summary['records_by_month'].items()):
                print(f"  {month}: {data['amount']:,.2f} Baht ({data['count']} records)")

        print("=" * 60)

    def export_to_json(self, records: List[Dict], filename: str = None) -> str:
        """Export records to JSON file."""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            vendor_suffix = f"_{self.vendor_id}" if self.vendor_id else ""
            filename = f"smt_budget{vendor_suffix}_{timestamp}.json"

        filepath = self.output_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

        print(f"Exported {len(records)} records to {filepath}")
        return str(filepath)

    def export_to_csv(self, records: List[Dict], filename: str = None) -> str:
        """Export records to CSV file."""
        if not records:
            print("No records to export")
            return None

        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            vendor_suffix = f"_{self.vendor_id}" if self.vendor_id else ""
            filename = f"smt_budget{vendor_suffix}_{timestamp}.csv"

        filepath = self.output_dir / filename

        # Select important fields for CSV export (must match save_to_database fields)
        fields = [
            'runDt', 'postingDate', 'refDocNo', 'vndrNo',
            'fundName', 'fundGroup', 'fundGroupDescr', 'fundDescr', 'efundDesc',
            'mouGrpCode', 'amount', 'wait', 'debt', 'bond', 'total',
            'bankNm', 'pmntStts', 'batchNo',
            'mophId', 'mophDesc', 'budgetSource'
        ]

        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(records)

        print(f"Exported {len(records)} records to {filepath}")
        return str(filepath)

    def save_to_database(self, records: List[Dict]) -> int:
        """
        Save records to database.

        This creates a new table 'smt_budget_transfers' if it doesn't exist.
        """
        try:
            from config.database import get_db_config, DB_TYPE
        except ImportError:
            stream_log("✗ Database configuration not available", 'error')
            return 0

        if not records:
            stream_log("No records to save", 'warning')
            return 0

        # Create database connection
        db_config = get_db_config()
        conn = None

        try:
            if DB_TYPE == 'postgresql':
                import psycopg2
                conn = psycopg2.connect(**db_config)
            else:  # mysql
                import pymysql
                conn = pymysql.connect(**db_config)
        except Exception as e:
            stream_log(f"✗ Could not connect to database: {e}", 'error')
            return 0

        if not conn:
            stream_log("✗ Could not connect to database", 'error')
            return 0

        cursor = conn.cursor()

        # Create table if not exists
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS smt_budget_transfers (
            id SERIAL PRIMARY KEY,
            run_date DATE,
            posting_date VARCHAR(20),
            batch_no VARCHAR(20),
            ref_doc_no VARCHAR(50),
            vendor_no VARCHAR(20),
            fund_name VARCHAR(100),
            fund_group INTEGER,
            fund_group_desc VARCHAR(100),
            fund_desc VARCHAR(200),
            efund_desc VARCHAR(200),
            mou_grp_code VARCHAR(20),
            amount DECIMAL(15,2),
            wait_amount DECIMAL(15,2),
            debt_amount DECIMAL(15,2),
            bond_amount DECIMAL(15,2),
            total_amount DECIMAL(15,2),
            bank_name VARCHAR(100),
            payment_status VARCHAR(10),
            budget_source VARCHAR(10),
            moph_id VARCHAR(50),
            moph_desc VARCHAR(200),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ref_doc_no, vendor_no, posting_date, mou_grp_code)
        )
        """

        if DB_TYPE == 'mysql':
            create_table_sql = create_table_sql.replace('SERIAL', 'INT AUTO_INCREMENT')
            create_table_sql = create_table_sql.replace('TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                                                        'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')

        try:
            cursor.execute(create_table_sql)
            conn.commit()
        except Exception as e:
            print(f"Note: Table may already exist: {e}")
            conn.rollback()

        # Insert records
        insert_count = 0

        if DB_TYPE == 'postgresql':
            insert_sql = """
            INSERT INTO smt_budget_transfers (
                run_date, posting_date, batch_no, ref_doc_no, vendor_no,
                fund_name, fund_group, fund_group_desc, fund_desc, efund_desc,
                mou_grp_code, amount, wait_amount, debt_amount, bond_amount,
                total_amount, bank_name, payment_status, budget_source,
                moph_id, moph_desc
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (ref_doc_no, vendor_no, posting_date, mou_grp_code)
            DO UPDATE SET
                amount = EXCLUDED.amount,
                total_amount = EXCLUDED.total_amount,
                payment_status = EXCLUDED.payment_status
            """
        else:  # MySQL
            insert_sql = """
            INSERT INTO smt_budget_transfers (
                run_date, posting_date, batch_no, ref_doc_no, vendor_no,
                fund_name, fund_group, fund_group_desc, fund_desc, efund_desc,
                mou_grp_code, amount, wait_amount, debt_amount, bond_amount,
                total_amount, bank_name, payment_status, budget_source,
                moph_id, moph_desc
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON DUPLICATE KEY UPDATE
                amount = VALUES(amount),
                total_amount = VALUES(total_amount),
                payment_status = VALUES(payment_status)
            """

        for record in records:
            try:
                # Handle numeric fields - convert empty strings to 0
                def to_decimal(val):
                    if val is None or val == '':
                        return 0
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        return 0

                def to_int(val):
                    if val is None or val == '':
                        return None
                    try:
                        return int(val)
                    except (ValueError, TypeError):
                        return None

                values = (
                    record.get('runDt') or None,
                    record.get('postingDate') or None,
                    record.get('batchNo') or None,
                    record.get('refDocNo') or None,
                    record.get('vndrNo') or None,
                    record.get('fundName') or None,
                    to_int(record.get('fundGroup')),
                    record.get('fundGroupDescr') or record.get('fundGroupDesc') or None,
                    record.get('fundDescr') or record.get('fundDesc') or None,
                    record.get('efundDesc') or None,
                    record.get('mouGrpCode') or None,
                    to_decimal(record.get('amount')),
                    to_decimal(record.get('wait')),
                    to_decimal(record.get('debt')),
                    to_decimal(record.get('bond')),
                    to_decimal(record.get('total')),
                    record.get('bankNm') or None,
                    record.get('pmntStts') or None,
                    record.get('budgetSource') or None,
                    record.get('mophId') or None,
                    record.get('mophDesc') or None,
                )
                cursor.execute(insert_sql, values)
                insert_count += 1
            except Exception as e:
                stream_log(f"  Error inserting record: {e}", 'error')
                continue

        conn.commit()
        cursor.close()
        conn.close()

        stream_log(f"✓ Saved {insert_count} records to database", 'success')
        return insert_count


def main():
    parser = argparse.ArgumentParser(
        description='Fetch budget/payment data from NHSO Smart Money Transfer (SMT) system',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --vendor-id 10670
  %(prog)s --vendor-id 10670 --budget-year 2569
  %(prog)s --start-date 01/10/2568 --end-date 10/01/2569
  %(prog)s --vendor-id 10670 --export csv
  %(prog)s --vendor-id 10670 --save-db
        """
    )

    parser.add_argument('--vendor-id', '-v',
                        help='Vendor/Hospital ID (5 or 10 digits)')
    parser.add_argument('--zone-id', '-z',
                        help='Zone ID (01-13)')
    parser.add_argument('--province-id', '-p',
                        help='Province ID (e.g., 4000)')
    parser.add_argument('--budget-year', '-y', type=int,
                        help='Budget year in Buddhist Era (e.g., 2569)')
    parser.add_argument('--start-date', '-s',
                        help='Start date in dd/mm/yyyy BE format (e.g., 01/10/2568)')
    parser.add_argument('--end-date', '-e',
                        help='End date in dd/mm/yyyy BE format (e.g., 10/01/2569)')
    parser.add_argument('--budget-source', '-b', default='',
                        help='Budget source filter (e.g., UC)')
    parser.add_argument('--export', choices=['json', 'csv'],
                        help='Export format (json or csv)')
    parser.add_argument('--save-db', action='store_true',
                        help='Save records to database')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Suppress summary output')

    args = parser.parse_args()

    # Validate required arguments
    if not args.vendor_id and not args.zone_id:
        print("Warning: No vendor ID or zone specified. This may return large datasets.")
        print("Consider using --vendor-id or --zone-id to filter results.\n")

    # Create fetcher
    fetcher = SMTBudgetFetcher(
        vendor_id=args.vendor_id,
        zone_id=args.zone_id,
        province_id=args.province_id
    )

    # Fetch data
    result = fetcher.fetch_budget_summary(
        budget_year=args.budget_year,
        start_date=args.start_date,
        end_date=args.end_date,
        budget_source=args.budget_source
    )

    records = result.get('datas', [])

    if not records:
        print("No records found")
        return 1

    # Calculate and print summary
    if not args.quiet:
        summary = fetcher.calculate_summary(records)
        fetcher.print_summary(summary)

    # Export if requested
    if args.export == 'json':
        fetcher.export_to_json(records)
    elif args.export == 'csv':
        fetcher.export_to_csv(records)

    # Save to database if requested
    if args.save_db:
        fetcher.save_to_database(records)

    return 0


if __name__ == '__main__':
    sys.exit(main())
