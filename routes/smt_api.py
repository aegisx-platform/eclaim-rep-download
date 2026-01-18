"""
SMT Budget API Routes

This blueprint handles all SMT (Smart Money Transfer) budget-related endpoints:
- SMT budget fetch from NHSO API
- SMT budget data download and export
- Fiscal year management
- Budget statistics and queries
- Database management (clear, stats)
"""

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required
from config.db_pool import get_connection as get_pooled_connection

# Create blueprint
smt_api_bp = Blueprint('smt_api', __name__)


def get_db_connection():
    """Get database connection from pool"""
    try:
        conn = get_pooled_connection()
        if conn is None:
            current_app.logger.error("Failed to get connection from pool")
        return conn
    except Exception as e:
        current_app.logger.error(f"Database connection error: {e}")
        return None


@smt_api_bp.route('/api/smt/fetch', methods=['POST'])
@login_required
def smt_fetch():
    """Trigger SMT budget fetch"""
    from utils.log_stream import log_streamer
    from utils.job_history_manager import job_history_manager

    settings_manager = current_app.config['settings_manager']

    # Check license feature access
    if not settings_manager.check_feature_access('smt_budget'):
        return jsonify({
            'success': False,
            'error': 'SMT Budget feature requires Basic tier or higher license',
            'upgrade_required': True,
            'current_tier': settings_manager.get_license_info().get('tier', 'trial')
        }), 403

    job_id = None
    try:
        data = request.get_json() or {}
        vendor_id = data.get('vendor_id')
        start_date = data.get('start_date')  # dd/mm/yyyy BE format
        end_date = data.get('end_date')  # dd/mm/yyyy BE format
        budget_year = data.get('budget_year')  # Buddhist Era year
        save_db = data.get('save_db', True)
        export_format = data.get('export_format')  # 'json' or 'csv' or None

        if not vendor_id:
            # Try to get from global hospital_code setting (falls back to legacy smt_vendor_id)
            vendor_id = settings_manager.get_hospital_code()

        if not vendor_id:
            return jsonify({'success': False, 'error': 'Vendor ID is required. Please configure Hospital Code in Settings.'}), 400

        # Start job tracking
        try:
            job_id = job_history_manager.start_job(
                job_type='download',
                job_subtype='smt_fetch',
                parameters={
                    'vendor_id': vendor_id,
                    'budget_year': budget_year,
                    'start_date': start_date,
                    'end_date': end_date,
                    'save_db': save_db
                },
                triggered_by='manual'
            )
        except Exception as e:
            current_app.logger.warning(f"Could not start job tracking: {e}")

        # Import and run fetcher
        from smt_budget_fetcher import SMTBudgetFetcher

        date_info = ""
        if start_date and end_date:
            date_info = f" ({start_date} - {end_date})"
        elif budget_year:
            date_info = f" (FY {budget_year})"

        log_streamer.write_log(
            f"Starting SMT fetch for vendor {vendor_id}{date_info}...",
            'info',
            'smt'
        )

        fetcher = SMTBudgetFetcher(vendor_id=vendor_id)
        result = fetcher.fetch_budget_summary(
            budget_year=int(budget_year) if budget_year else None,
            start_date=start_date,
            end_date=end_date
        )
        records = result.get('datas', [])

        if not records:
            log_streamer.write_log(
                f"No records found for vendor {vendor_id}",
                'warning',
                'smt'
            )
            return jsonify({
                'success': True,
                'message': 'No records found',
                'records': 0
            })

        # Calculate summary
        summary = fetcher.calculate_summary(records)

        # Debug: show vendor_no format from first record
        if records:
            first_record = records[0]
            print(f"[DEBUG] SMT fetch - vendor_no format from API: vndrNo='{first_record.get('vndrNo')}'")

        # Save to database if requested
        saved_count = 0
        if save_db:
            saved_count = fetcher.save_to_database(records)
            log_streamer.write_log(
                f"Saved {saved_count} records to database",
                'success',
                'smt'
            )

        # Export if requested
        export_path = None
        if export_format == 'json':
            export_path = fetcher.export_to_json(records)
        elif export_format == 'csv':
            export_path = fetcher.export_to_csv(records)

        log_streamer.write_log(
            f"✓ SMT fetch completed: {len(records)} records, {summary['total_amount']:,.2f} Baht",
            'success',
            'smt'
        )

        # Complete job tracking
        if job_id:
            try:
                job_history_manager.complete_job(
                    job_id=job_id,
                    status='completed',
                    results={
                        'records': len(records),
                        'saved': saved_count,
                        'total_amount': summary['total_amount'],
                        'vendor_id': vendor_id,
                        'budget_year': budget_year
                    }
                )
            except Exception as e:
                current_app.logger.warning(f"Could not complete job tracking: {e}")

        return jsonify({
            'success': True,
            'records': len(records),
            'saved': saved_count,
            'total_amount': summary['total_amount'],
            'export_path': export_path
        })

    except Exception as e:
        # Mark job as failed
        if job_id:
            try:
                job_history_manager.complete_job(
                    job_id=job_id,
                    status='failed',
                    error_message=str(e)
                )
            except Exception:
                pass
        log_streamer.write_log(
            f"✗ SMT fetch failed: {str(e)}",
            'error',
            'smt'
        )
        return jsonify({'success': False, 'error': str(e)}), 500


@smt_api_bp.route('/api/smt/fiscal-years')
@login_required
def api_smt_fiscal_years():
    """Get available fiscal years in database"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Get distinct fiscal years from posting_date
        cursor.execute("""
            SELECT DISTINCT fiscal_year
            FROM smt_budget
            WHERE fiscal_year IS NOT NULL
            ORDER BY fiscal_year DESC
        """)

        rows = cursor.fetchall()
        fiscal_years = [r[0] for r in rows if r[0] and r[0] > 2500]

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'fiscal_years': fiscal_years
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'fiscal_years': []}), 200


@smt_api_bp.route('/api/smt/data')
@login_required
def api_smt_data():
    """Get SMT budget data from database with optional date filtering"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        fund_group = request.args.get('fund_group')
        start_date = request.args.get('start_date')  # Format: dd/mm/yyyy BE
        end_date = request.args.get('end_date')      # Format: dd/mm/yyyy BE

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Helper function to convert dd/mm/yyyy to sortable yyyymmdd format
        def to_sortable(date_str):
            if not date_str or len(date_str) < 10:
                return None
            parts = date_str.split('/')
            if len(parts) == 3:
                return f"{parts[2]}{parts[1]}{parts[0]}"
            return None

        # Build query with parameterized values
        conditions = []
        params = []

        if fund_group:
            conditions.append("fund_group_desc = %s")
            params.append(fund_group)

        # Convert dates to sortable format for string comparison
        # posting_date can be stored as:
        # - "25671227" (yyyymmdd) - 8 digits, already sortable
        # - "27/12/2567" (dd/mm/yyyy) - 10 chars, need transformation
        # We use CASE to handle both formats
        sortable_posting_date_expr = """
            CASE
                WHEN LENGTH(posting_date) = 8 THEN posting_date
                WHEN LENGTH(posting_date) = 10 THEN CONCAT(RIGHT(posting_date, 4), SUBSTRING(posting_date, 4, 2), SUBSTRING(posting_date, 1, 2))
                ELSE posting_date
            END
        """

        if start_date:
            sortable_start = to_sortable(start_date)
            if sortable_start:
                conditions.append(f"({sortable_posting_date_expr}) >= %s")
                params.append(sortable_start)

        if end_date:
            sortable_end = to_sortable(end_date)
            if sortable_end:
                conditions.append(f"({sortable_posting_date_expr}) <= %s")
                params.append(sortable_end)

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        # Get total count
        count_query = "SELECT COUNT(*) FROM smt_budget_transfers " + where_clause
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]

        # Get paginated data - order by sortable date format
        offset = (page - 1) * per_page
        sortable_order_expr = """
            CASE
                WHEN LENGTH(posting_date) = 8 THEN posting_date
                WHEN LENGTH(posting_date) = 10 THEN CONCAT(RIGHT(posting_date, 4), SUBSTRING(posting_date, 4, 2), SUBSTRING(posting_date, 1, 2))
                ELSE posting_date
            END
        """
        select_query = """
            SELECT id, run_date, posting_date, ref_doc_no, vendor_no,
                   fund_name, fund_group_desc, amount, total_amount,
                   bank_name, payment_status, created_at
            FROM smt_budget_transfers
            """ + where_clause + f"""
            ORDER BY ({sortable_order_expr}) DESC, id DESC
            LIMIT %s OFFSET %s
        """
        cursor.execute(select_query, params + [per_page, offset])

        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        data = [
            {
                'id': r[0],
                'run_date': str(r[1]) if r[1] else None,
                'posting_date': r[2],
                'ref_doc_no': r[3],
                'vendor_no': r[4],
                'fund_name': r[5],
                'fund_group_desc': r[6],
                'amount': float(r[7] or 0),
                'total_amount': float(r[8] or 0),
                'bank_name': r[9],
                'payment_status': r[10],
                'created_at': r[11].isoformat() if r[11] else None
            }
            for r in rows
        ]

        return jsonify({
            'success': True,
            'data': data,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@smt_api_bp.route('/api/smt/stats')
@login_required
def api_smt_stats():
    """Get SMT budget statistics (record count and last sync time)"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': True, 'record_count': 0, 'last_sync': None})

        cursor = conn.cursor()

        # Get total record count
        cursor.execute("SELECT COUNT(*) FROM smt_budget_transfers")
        record_count = cursor.fetchone()[0]

        # Get last sync time (most recent created_at)
        cursor.execute("SELECT MAX(created_at) FROM smt_budget_transfers")
        last_sync_result = cursor.fetchone()[0]
        last_sync = str(last_sync_result) if last_sync_result else None

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'record_count': record_count,
            'last_sync': last_sync
        })

    except Exception as e:
        return jsonify({'success': True, 'record_count': 0, 'last_sync': None})


@smt_api_bp.route('/api/smt/clear', methods=['POST'])
@login_required
def api_smt_clear():
    """Clear all SMT budget data from database"""
    from utils.log_stream import log_streamer

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Delete all SMT budget transfers
        cursor.execute("DELETE FROM smt_budget_transfers")
        deleted_count = cursor.rowcount

        conn.commit()
        cursor.close()
        conn.close()

        log_streamer.write_log(f"Cleared {deleted_count} SMT budget records", 'info', 'smt')

        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'message': f'Deleted {deleted_count} records'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@smt_api_bp.route('/api/smt/download', methods=['POST'])
@login_required
def api_smt_download():
    """Download SMT budget data and export to CSV, with optional auto-import to database"""
    from utils.log_stream import log_streamer
    from utils.job_history_manager import job_history_manager

    settings_manager = current_app.config['settings_manager']

    job_id = None
    try:
        data = request.get_json() or {}
        vendor_id = data.get('vendor_id')
        start_date = data.get('start_date')  # dd/mm/yyyy BE format
        end_date = data.get('end_date')      # dd/mm/yyyy BE format
        budget_source = data.get('budget_source', '')  # UC, OF, SS, LG, or empty for all
        budget_type = data.get('budget_type', '')      # OP, IP, PP, or empty for all
        auto_import = data.get('auto_import', False)   # Auto-import to database after download

        # Vendor ID is optional - empty means all in region
        if not vendor_id:
            # Try to get from global hospital_code setting (falls back to legacy smt_vendor_id)
            default_vendor = settings_manager.get_hospital_code()
            # Only use default if vendor_id is not explicitly provided as empty string
            if vendor_id is None and default_vendor:
                vendor_id = default_vendor

        # Start job tracking
        try:
            job_id = job_history_manager.start_job(
                job_type='download',
                job_subtype='smt',
                parameters={
                    'vendor_id': vendor_id,
                    'start_date': start_date,
                    'end_date': end_date,
                    'budget_source': budget_source,
                    'auto_import': auto_import
                },
                triggered_by='manual'
            )
        except Exception as e:
            current_app.logger.warning(f"Could not start job tracking: {e}")

        # Import and run fetcher
        from smt_budget_fetcher import SMTBudgetFetcher

        vendor_display = vendor_id if vendor_id else 'ทั้งหมด (All)'
        log_streamer.write_log(
            f"Starting SMT download for vendor {vendor_display} ({start_date} - {end_date})...",
            'info',
            'smt'
        )

        fetcher = SMTBudgetFetcher(vendor_id=vendor_id if vendor_id else None)
        result = fetcher.fetch_budget_summary(
            start_date=start_date,
            end_date=end_date,
            budget_source=budget_source
        )
        records = result.get('datas', [])

        if not records:
            return jsonify({
                'success': True,
                'message': 'No records found',
                'records': 0
            })

        # Calculate summary
        summary = fetcher.calculate_summary(records)

        # Auto-import to database if requested
        imported_count = 0
        new_records = 0
        export_path = None

        if auto_import:
            # Count records before import to detect new records
            count_before = 0
            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM smt_budget_transfers")
                    count_before = cursor.fetchone()[0]
                    cursor.close()
                    conn.close()
            except Exception:
                pass

            log_streamer.write_log(
                f"Auto-importing {len(records)} records to database...",
                'info',
                'smt'
            )
            imported_count = fetcher.save_to_database(records)

            # Count after import to detect new records
            count_after = 0
            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM smt_budget_transfers")
                    count_after = cursor.fetchone()[0]
                    cursor.close()
                    conn.close()
            except Exception:
                pass

            new_records = count_after - count_before

            # Only create CSV if there are new records
            if new_records > 0:
                export_path = fetcher.export_to_csv(records)
                log_streamer.write_log(
                    f"✓ {new_records} new records, exported to {export_path}",
                    'success',
                    'smt'
                )
            else:
                log_streamer.write_log(
                    f"✓ No new records (all {len(records)} already exist), skipping CSV export",
                    'info',
                    'smt'
                )

            message = f'Fetched {len(records)} records: {new_records} new, {len(records) - new_records} existing'
        else:
            # Without auto-import, always create CSV
            export_path = fetcher.export_to_csv(records)
            message = f'Downloaded {len(records)} records'

        log_streamer.write_log(
            f"✓ SMT download completed",
            'success',
            'smt'
        )

        # Complete job tracking
        if job_id:
            try:
                job_history_manager.complete_job(
                    job_id=job_id,
                    status='completed',
                    results={
                        'records': len(records),
                        'new_records': new_records,
                        'imported': imported_count,
                        'total_amount': summary['total_amount'],
                        'export_path': export_path
                    }
                )
            except Exception as e:
                current_app.logger.warning(f"Could not complete job tracking: {e}")

        return jsonify({
            'success': True,
            'message': message,
            'records': len(records),
            'new_records': new_records,
            'imported': imported_count,
            'total_amount': summary['total_amount'],
            'export_path': export_path
        })

    except Exception as e:
        # Mark job as failed
        if job_id:
            try:
                job_history_manager.complete_job(
                    job_id=job_id,
                    status='failed',
                    error_message=str(e)
                )
            except Exception:
                pass
        log_streamer.write_log(f"✗ SMT download failed: {str(e)}", 'error', 'smt')
        return jsonify({'success': False, 'error': str(e)}), 500
