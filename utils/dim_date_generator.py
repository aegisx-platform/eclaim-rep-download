#!/usr/bin/env python3
"""
Date Dimension Generator
Generates date dimension data for data warehouse analytics
Supports Thai Buddhist calendar and fiscal year
"""

import os
import sys
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.database import get_db_config, DB_TYPE

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DimDateGenerator:
    """Generate date dimension data"""

    # Thai month names
    THAI_MONTHS = {
        1: 'มกราคม', 2: 'กุมภาพันธ์', 3: 'มีนาคม', 4: 'เมษายน',
        5: 'พฤษภาคม', 6: 'มิถุนายน', 7: 'กรกฎาคม', 8: 'สิงหาคม',
        9: 'กันยายน', 10: 'ตุลาคม', 11: 'พฤศจิกายน', 12: 'ธันวาคม'
    }

    # Thai day names
    THAI_DAYS = {
        0: 'วันจันทร์', 1: 'วันอังคาร', 2: 'วันพุธ', 3: 'วันพฤหัสบดี',
        4: 'วันศุกร์', 5: 'วันเสาร์', 6: 'วันอาทิตย์'
    }

    # English month names
    ENGLISH_MONTHS = {
        1: 'January', 2: 'February', 3: 'March', 4: 'April',
        5: 'May', 6: 'June', 7: 'July', 8: 'August',
        9: 'September', 10: 'October', 11: 'November', 12: 'December'
    }

    # English day names
    ENGLISH_DAYS = {
        0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday',
        4: 'Friday', 5: 'Saturday', 6: 'Sunday'
    }

    # Thai public holidays (fixed dates only)
    THAI_HOLIDAYS = {
        (1, 1): 'วันขึ้นปีใหม่',
        (4, 6): 'วันจักรี',
        (5, 1): 'วันแรงงานแห่งชาติ',
        (5, 4): 'วันฉัตรมงคล',
        (7, 28): 'วันเฉลิมพระชนมพรรษาพระบาทสมเด็จพระเจ้าอยู่หัว',
        (8, 12): 'วันเฉลิมพระชนมพรรษาสมเด็จพระนางเจ้าฯ พระบรมราชินี',
        (10, 13): 'วันคล้ายวันสวรรคตพระบาทสมเด็จพระบรมชนกาธิเบศร มหาภูมิพลอดุลยเดชมหาราช บรมนาถบพิตร',
        (10, 23): 'วันปิยมหาราช',
        (12, 5): 'วันคล้ายวันพระบรมราชสมภพพระบาทสมเด็จพระบรมชนกาธิเบศร มหาภูมิพลอดุลยเดชมหาราช บรมนาถบพิตร',
        (12, 10): 'วันรัฐธรรมนูญ',
        (12, 31): 'วันสิ้นปี'
    }

    def __init__(self):
        self.conn = None
        self.cursor = None

    def connect(self) -> bool:
        """Connect to database"""
        try:
            db_config = get_db_config()

            if DB_TYPE == 'postgresql':
                import psycopg2
                self.conn = psycopg2.connect(**db_config)
            else:  # mysql
                import pymysql
                self.conn = pymysql.connect(**db_config)

            self.cursor = self.conn.cursor()
            return True
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            return False

    def disconnect(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    def get_fiscal_year(self, date: datetime) -> int:
        """
        Calculate Thai fiscal year (starts October 1)

        Args:
            date: Date to calculate fiscal year for

        Returns:
            Fiscal year (Gregorian calendar)
        """
        if date.month >= 10:
            return date.year + 1
        return date.year

    def get_fiscal_quarter(self, date: datetime) -> int:
        """
        Calculate fiscal quarter (Thai fiscal year starts Oct 1)

        Q1: Oct-Dec
        Q2: Jan-Mar
        Q3: Apr-Jun
        Q4: Jul-Sep

        Args:
            date: Date to calculate quarter for

        Returns:
            Fiscal quarter (1-4)
        """
        month = date.month
        if 10 <= month <= 12:
            return 1
        elif 1 <= month <= 3:
            return 2
        elif 4 <= month <= 6:
            return 3
        else:  # 7-9
            return 4

    def get_calendar_quarter(self, date: datetime) -> int:
        """
        Calculate calendar quarter

        Args:
            date: Date to calculate quarter for

        Returns:
            Calendar quarter (1-4)
        """
        return (date.month - 1) // 3 + 1

    def is_holiday(self, date: datetime) -> Tuple[bool, Optional[str]]:
        """
        Check if date is a Thai public holiday

        Args:
            date: Date to check

        Returns:
            Tuple of (is_holiday, holiday_name)
        """
        key = (date.month, date.day)
        if key in self.THAI_HOLIDAYS:
            return True, self.THAI_HOLIDAYS[key]
        return False, None

    def generate_date_record(self, date: datetime) -> dict:
        """
        Generate complete date dimension record

        Args:
            date: Date to generate record for

        Returns:
            Dictionary with all date dimension fields
        """
        # Calculate various attributes
        year = date.year
        year_be = year + 543  # Buddhist Era
        month = date.month
        day = date.day
        day_of_week = date.weekday()  # 0=Monday
        day_of_year = date.timetuple().tm_yday
        week_of_year = date.isocalendar()[1]

        fiscal_year = self.get_fiscal_year(date)
        fiscal_year_be = fiscal_year + 543
        fiscal_quarter = self.get_fiscal_quarter(date)
        calendar_quarter = self.get_calendar_quarter(date)

        is_weekend = day_of_week in [5, 6]  # Saturday, Sunday
        is_holiday, holiday_name = self.is_holiday(date)

        # Generate date_id (YYYYMMDD format)
        date_id = int(date.strftime('%Y%m%d'))

        return {
            'date_id': date_id,
            'full_date': date.strftime('%Y-%m-%d'),
            'day_of_week': day_of_week,
            'day_name': self.ENGLISH_DAYS[day_of_week],
            'day_of_month': day,
            'day_of_year': day_of_year,
            'week_of_year': week_of_year,
            'month_number': month,
            'month_name': self.ENGLISH_MONTHS[month],
            'month_name_th': self.THAI_MONTHS[month],
            'quarter': calendar_quarter,
            'year': year,
            'fiscal_year': fiscal_year,
            'fiscal_quarter': fiscal_quarter,
            'is_weekend': is_weekend,
            'is_holiday': is_holiday,
            'holiday_name': holiday_name
        }

    def get_existing_date_range(self) -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        Get the current date range in dim_date table

        Returns:
            Tuple of (earliest_date, latest_date) or (None, None) if table is empty
        """
        try:
            self.cursor.execute("""
                SELECT MIN(full_date) as earliest, MAX(full_date) as latest
                FROM dim_date
            """)
            row = self.cursor.fetchone()
            if row and row[0] and row[1]:
                earliest = row[0]
                latest = row[1]

                # Convert to datetime if they are date objects (MySQL returns date)
                if not isinstance(earliest, datetime):
                    earliest = datetime.combine(earliest, datetime.min.time())
                if not isinstance(latest, datetime):
                    latest = datetime.combine(latest, datetime.min.time())

                return earliest, latest
            return None, None
        except Exception as e:
            logger.error(f"Error getting existing date range: {e}")
            return None, None

    def generate_dates(self, start_year: int, end_year: int, check_existing: bool = True) -> List[dict]:
        """
        Generate date dimension records for a year range

        Args:
            start_year: Start year (Gregorian)
            end_year: End year (Gregorian) inclusive
            check_existing: Skip dates that already exist in database

        Returns:
            List of date records
        """
        records = []
        existing_dates = set()

        # Get existing dates if checking
        if check_existing and self.conn:
            try:
                self.cursor.execute("""
                    SELECT full_date FROM dim_date
                    WHERE year >= %s AND year <= %s
                """, (start_year, end_year))
                existing_dates = {row[0] for row in self.cursor.fetchall()}
                logger.info(f"Found {len(existing_dates)} existing dates in range")
            except Exception as e:
                logger.warning(f"Could not check existing dates: {e}")

        # Generate dates
        start_date = datetime(start_year, 1, 1)
        end_date = datetime(end_year, 12, 31)
        current_date = start_date

        while current_date <= end_date:
            # Skip if already exists
            if check_existing and current_date.date() in existing_dates:
                current_date += timedelta(days=1)
                continue

            record = self.generate_date_record(current_date)
            records.append(record)
            current_date += timedelta(days=1)

        logger.info(f"Generated {len(records)} new date records")
        return records

    def insert_records(self, records: List[dict]) -> int:
        """
        Insert date records into database

        Args:
            records: List of date records

        Returns:
            Number of records inserted
        """
        if not records:
            logger.info("No records to insert")
            return 0

        try:
            # Build insert query
            insert_sql = """
                INSERT INTO dim_date (
                    date_id, full_date, day_of_week, day_name, day_of_month,
                    day_of_year, week_of_year, month_number, month_name, month_name_th,
                    quarter, year, fiscal_year, fiscal_quarter,
                    is_weekend, is_holiday, holiday_name
                ) VALUES (
                    %(date_id)s, %(full_date)s, %(day_of_week)s, %(day_name)s, %(day_of_month)s,
                    %(day_of_year)s, %(week_of_year)s, %(month_number)s, %(month_name)s, %(month_name_th)s,
                    %(quarter)s, %(year)s, %(fiscal_year)s, %(fiscal_quarter)s,
                    %(is_weekend)s, %(is_holiday)s, %(holiday_name)s
                )
            """

            # Insert in batches
            batch_size = 100
            total_inserted = 0

            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                self.cursor.executemany(insert_sql, batch)
                total_inserted += len(batch)

                if (i + batch_size) % 1000 == 0:
                    logger.info(f"Inserted {total_inserted}/{len(records)} records...")

            self.conn.commit()
            logger.info(f"✓ Successfully inserted {total_inserted} records")
            return total_inserted

        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error inserting records: {e}")
            raise

    def extend_to_year(self, target_year: int) -> int:
        """
        Extend date dimension to target year

        Args:
            target_year: Target year (Gregorian) to extend to

        Returns:
            Number of records added
        """
        if not self.connect():
            raise Exception("Failed to connect to database")

        try:
            # Get current range
            earliest, latest = self.get_existing_date_range()

            if latest is None:
                # Table is empty, generate from current year to target
                start_year = datetime.now().year
                logger.info(f"Table is empty. Generating {start_year}-{target_year}")
            else:
                # Extend from latest date
                start_year = latest.year
                if latest < datetime(latest.year, 12, 31):
                    # Latest is not end of year, start from same year
                    pass
                else:
                    # Latest is end of year, start from next year
                    start_year += 1

                if start_year > target_year:
                    logger.info(f"Already have data up to {latest.year}, no extension needed")
                    return 0

                logger.info(f"Extending from {start_year} to {target_year}")

            # Generate and insert
            records = self.generate_dates(start_year, target_year, check_existing=True)
            count = self.insert_records(records)

            return count

        finally:
            self.disconnect()


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Generate date dimension data')
    parser.add_argument('--start-year', type=int, help='Start year (Gregorian)')
    parser.add_argument('--end-year', type=int, help='End year (Gregorian)')
    parser.add_argument('--extend-to', type=int, help='Extend to target year')
    parser.add_argument('--status', action='store_true', help='Show current coverage')

    args = parser.parse_args()

    generator = DimDateGenerator()

    # Show status
    if args.status:
        if not generator.connect():
            logger.error("Failed to connect to database")
            return 1

        try:
            earliest, latest = generator.get_existing_date_range()
            if earliest and latest:
                generator.cursor.execute("SELECT COUNT(*) FROM dim_date")
                count = generator.cursor.fetchone()[0]

                print("\n" + "="*60)
                print("Date Dimension Status")
                print("="*60)
                print(f"Earliest date: {earliest} (BE {earliest.year + 543})")
                print(f"Latest date:   {latest} (BE {latest.year + 543})")
                print(f"Total records: {count:,}")
                print(f"Coverage:      {(latest - earliest).days + 1:,} days")
                print("="*60 + "\n")
            else:
                print("\nDate dimension table is empty\n")
        finally:
            generator.disconnect()
        return 0

    # Extend to target year
    if args.extend_to:
        try:
            count = generator.extend_to_year(args.extend_to)
            print(f"\n✓ Extended date dimension by {count} records to year {args.extend_to}")
            return 0
        except Exception as e:
            logger.error(f"Failed to extend: {e}")
            return 1

    # Generate for year range
    if args.start_year and args.end_year:
        if not generator.connect():
            logger.error("Failed to connect to database")
            return 1

        try:
            records = generator.generate_dates(args.start_year, args.end_year, check_existing=True)
            count = generator.insert_records(records)
            print(f"\n✓ Generated and inserted {count} records for years {args.start_year}-{args.end_year}")
            return 0
        except Exception as e:
            logger.error(f"Failed to generate: {e}")
            return 1
        finally:
            generator.disconnect()

    # Default: extend to 2 years from now
    target_year = datetime.now().year + 2
    try:
        count = generator.extend_to_year(target_year)
        if count > 0:
            print(f"\n✓ Extended date dimension by {count} records to year {target_year}")
        else:
            print(f"\n✓ Date dimension already covers up to {target_year}")
        return 0
    except Exception as e:
        logger.error(f"Failed: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
