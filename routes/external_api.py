"""
External API Routes (v1)
REST API for hospital HIS integration
"""

from flask import Blueprint, jsonify, request
from utils.api_auth import require_api_key
from config.database import get_db_config, DB_TYPE
from datetime import datetime
import logging

if DB_TYPE == 'postgresql':
    import psycopg2
    from psycopg2.extras import RealDictCursor
else:
    import pymysql
    import pymysql.cursors

# Create blueprint
external_api_bp = Blueprint('external_api', __name__, url_prefix='/api/v1')

logger = logging.getLogger(__name__)

# ==================== Health Check ====================

@external_api_bp.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint (no authentication required)

    GET /api/v1/health
    """
    return jsonify({
        'success': True,
        'message': 'API is healthy',
        'version': '1.0.0',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })


# ==================== Claims Data ====================

@external_api_bp.route('/claims', methods=['GET'])
@require_api_key
def get_claims():
    """
    Get claims data with filters

    GET /api/v1/claims?date_from=2025-12-01&date_to=2025-12-31&scheme=UCS&page=1&per_page=100

    Query Parameters:
        - date_from (required): Start date (YYYY-MM-DD)
        - date_to (required): End date (YYYY-MM-DD)
        - scheme (optional): Scheme code (UCS, OFC, SSS, LGO)
        - hn (optional): Hospital number
        - pid (optional): Personal ID
        - page (optional, default=1): Page number
        - per_page (optional, default=100, max=1000): Items per page
    """
    try:
        # Validate required parameters
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')

        if not date_from or not date_to:
            return jsonify({
                'success': False,
                'error': 'date_from and date_to are required',
                'code': 'INVALID_PARAMS'
            }), 400

        # Optional filters
        scheme = request.args.get('scheme', '').upper() if request.args.get('scheme') else None
        hn = request.args.get('hn')
        pid = request.args.get('pid')

        # Pagination
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 100)), 1000)
        offset = (page - 1) * per_page

        # Build query
        where_clauses = ["dateadm BETWEEN %s AND %s"]
        params = [date_from, date_to]

        if scheme:
            where_clauses.append("UPPER(SUBSTRING(rep_no, 1, 3)) = %s")
            params.append(scheme)

        if hn:
            where_clauses.append("hn = %s")
            params.append(hn)

        if pid:
            where_clauses.append("pid = %s")
            params.append(pid)

        where_sql = " AND ".join(where_clauses)

        # Connect to database
        conn = None
        cursor = None

        if DB_TYPE == 'postgresql':
            conn = psycopg2.connect(**get_db_config())
            cursor = conn.cursor(cursor_factory=RealDictCursor)
        else:
            conn = pymysql.connect(**get_db_config())
            cursor = conn.cursor(pymysql.cursors.DictCursor)

        # Get total count
        cursor.execute(f"""
            SELECT COUNT(*) as total
            FROM claim_rep_opip_nhso_item
            WHERE {where_sql}
        """, params)

        total = cursor.fetchone()['total']
        total_pages = (total + per_page - 1) // per_page

        # Get data
        cursor.execute(f"""
            SELECT
                tran_id,
                file_id,
                hn,
                pid,
                dateadm,
                datedsc,
                an,
                rep_no,
                claim_net as total_approve,
                hcode,
                hmain,
                his_matched,
                his_vn,
                reconcile_status
            FROM claim_rep_opip_nhso_item
            WHERE {where_sql}
            ORDER BY dateadm DESC, tran_id
            LIMIT %s OFFSET %s
        """, params + [per_page, offset])

        items = cursor.fetchall()

        cursor.close()
        conn.close()

        # Format response
        formatted_items = []
        for item in items:
            formatted_item = dict(item)
            # Convert dates to strings
            if formatted_item.get('dateadm'):
                formatted_item['dateadm'] = formatted_item['dateadm'].strftime('%Y-%m-%d')
            if formatted_item.get('datedsc'):
                formatted_item['datedsc'] = formatted_item['datedsc'].strftime('%Y-%m-%d')
            # Convert Decimal to float
            if formatted_item.get('total_approve'):
                formatted_item['total_approve'] = float(formatted_item['total_approve'])
            formatted_items.append(formatted_item)

        return jsonify({
            'success': True,
            'data': {
                'items': formatted_items,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': total_pages
                }
            }
        })

    except Exception as e:
        logger.error(f"Error getting claims: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'code': 'INTERNAL_ERROR'
        }), 500


@external_api_bp.route('/claims/<tran_id>', methods=['GET'])
@require_api_key
def get_claim_by_id(tran_id):
    """
    Get single claim by TRAN_ID

    GET /api/v1/claims/{tran_id}
    """
    try:
        conn = None
        cursor = None

        if DB_TYPE == 'postgresql':
            conn = psycopg2.connect(**get_db_config())
            cursor = conn.cursor(cursor_factory=RealDictCursor)
        else:
            conn = pymysql.connect(**get_db_config())
            cursor = conn.cursor(pymysql.cursors.DictCursor)

        cursor.execute("""
            SELECT
                tran_id, file_id, hn, pid, dateadm, datedsc,
                an, rep_no, claim_net as total_approve, hcode, hmain,
                his_matched, his_vn, reconcile_status
            FROM claim_rep_opip_nhso_item
            WHERE tran_id = %s
        """, (tran_id,))

        item = cursor.fetchone()

        cursor.close()
        conn.close()

        if not item:
            return jsonify({
                'success': False,
                'error': 'Claim not found',
                'code': 'NOT_FOUND'
            }), 404

        # Format response
        formatted_item = dict(item)
        if formatted_item.get('dateadm'):
            formatted_item['dateadm'] = formatted_item['dateadm'].strftime('%Y-%m-%d')
        if formatted_item.get('datedsc'):
            formatted_item['datedsc'] = formatted_item['datedsc'].strftime('%Y-%m-%d')
        if formatted_item.get('total_approve'):
            formatted_item['total_approve'] = float(formatted_item['total_approve'])

        return jsonify({
            'success': True,
            'data': formatted_item
        })

    except Exception as e:
        logger.error(f"Error getting claim: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'code': 'INTERNAL_ERROR'
        }), 500


@external_api_bp.route('/claims/summary', methods=['GET'])
@require_api_key
def get_claims_summary():
    """
    Get claims summary statistics

    GET /api/v1/claims/summary?date_from=2025-12-01&date_to=2025-12-31
    """
    try:
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')

        if not date_from or not date_to:
            return jsonify({
                'success': False,
                'error': 'date_from and date_to are required',
                'code': 'INVALID_PARAMS'
            }), 400

        conn = None
        cursor = None

        if DB_TYPE == 'postgresql':
            conn = psycopg2.connect(**get_db_config())
            cursor = conn.cursor(cursor_factory=RealDictCursor)
        else:
            conn = pymysql.connect(**get_db_config())
            cursor = conn.cursor(pymysql.cursors.DictCursor)

        # Get overall summary
        cursor.execute("""
            SELECT
                COUNT(*) as total_claims,
                SUM(claim_net) as total_amount
            FROM claim_rep_opip_nhso_item
            WHERE dateadm BETWEEN %s AND %s
        """, (date_from, date_to))

        summary = cursor.fetchone()

        # Get by scheme
        cursor.execute("""
            SELECT
                SUBSTRING(rep_no, 1, 3) as scheme,
                COUNT(*) as count,
                SUM(claim_net) as amount
            FROM claim_rep_opip_nhso_item
            WHERE dateadm BETWEEN %s AND %s
            GROUP BY SUBSTRING(rep_no, 1, 3)
        """, (date_from, date_to))

        schemes = cursor.fetchall()

        # Get reconciliation stats
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN his_matched = TRUE THEN 1 ELSE 0 END) as matched,
                SUM(CASE WHEN his_matched = FALSE OR his_matched IS NULL THEN 1 ELSE 0 END) as unmatched
            FROM claim_rep_opip_nhso_item
            WHERE dateadm BETWEEN %s AND %s
        """, (date_from, date_to))

        recon = cursor.fetchone()

        cursor.close()
        conn.close()

        # Format response
        by_scheme = {}
        for scheme in schemes:
            scheme_code = (scheme['scheme'] or 'UNKNOWN').upper()
            by_scheme[scheme_code] = {
                'count': int(scheme['count']),
                'amount': float(scheme['amount'] or 0)
            }

        match_rate = float(recon['matched']) / float(recon['total']) if recon['total'] > 0 else 0

        return jsonify({
            'success': True,
            'data': {
                'total_claims': int(summary['total_claims'] or 0),
                'total_amount': float(summary['total_amount'] or 0),
                'by_scheme': by_scheme,
                'reconciliation': {
                    'matched': int(recon['matched'] or 0),
                    'unmatched': int(recon['unmatched'] or 0),
                    'match_rate': round(match_rate, 4)
                }
            }
        })

    except Exception as e:
        logger.error(f"Error getting claims summary: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'code': 'INTERNAL_ERROR'
        }), 500


# ==================== Reconciliation ====================

@external_api_bp.route('/reconciliation/match', methods=['POST'])
@require_api_key
def reconciliation_match():
    """
    Match claims with HIS data

    POST /api/v1/reconciliation/match
    Body: {
        "matches": [
            {
                "tran_id": "1234567890",
                "his_vn": "6512000001",
                "his_hn": "12345678",
                "his_an": "65120001"
            }
        ]
    }
    """
    try:
        data = request.get_json()

        if not data or 'matches' not in data:
            return jsonify({
                'success': False,
                'error': 'matches array is required',
                'code': 'INVALID_PARAMS'
            }), 400

        matches = data['matches']

        if not isinstance(matches, list) or len(matches) == 0:
            return jsonify({
                'success': False,
                'error': 'matches must be a non-empty array',
                'code': 'INVALID_PARAMS'
            }), 400

        conn = None
        cursor = None

        if DB_TYPE == 'postgresql':
            conn = psycopg2.connect(**get_db_config())
            cursor = conn.cursor()
        else:
            conn = pymysql.connect(**get_db_config())
            cursor = conn.cursor()

        results = []
        matched_count = 0
        failed_count = 0

        for match in matches:
            tran_id = match.get('tran_id')
            his_vn = match.get('his_vn')
            his_hn = match.get('his_hn')
            his_an = match.get('his_an')

            if not tran_id:
                results.append({
                    'tran_id': None,
                    'status': 'failed',
                    'error': 'tran_id is required'
                })
                failed_count += 1
                continue

            try:
                # Update claim with HIS data
                cursor.execute("""
                    UPDATE claim_rep_opip_nhso_item
                    SET
                        his_vn = %s,
                        his_matched = TRUE,
                        reconcile_status = 'matched'
                    WHERE tran_id = %s
                """, (his_vn, tran_id))

                if cursor.rowcount > 0:
                    results.append({
                        'tran_id': tran_id,
                        'status': 'matched',
                        'his_vn': his_vn
                    })
                    matched_count += 1
                else:
                    results.append({
                        'tran_id': tran_id,
                        'status': 'failed',
                        'error': 'TRAN_ID not found'
                    })
                    failed_count += 1

            except Exception as e:
                results.append({
                    'tran_id': tran_id,
                    'status': 'failed',
                    'error': str(e)
                })
                failed_count += 1

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'data': {
                'matched': matched_count,
                'failed': failed_count,
                'results': results
            }
        })

    except Exception as e:
        logger.error(f"Error matching reconciliation: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'code': 'INTERNAL_ERROR'
        }), 500


@external_api_bp.route('/reconciliation/status', methods=['GET'])
@require_api_key
def reconciliation_status():
    """
    Get reconciliation status

    GET /api/v1/reconciliation/status?date_from=2025-12-01&date_to=2025-12-31
    """
    try:
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')

        conn = None
        cursor = None

        if DB_TYPE == 'postgresql':
            conn = psycopg2.connect(**get_db_config())
            cursor = conn.cursor(cursor_factory=RealDictCursor)
        else:
            conn = pymysql.connect(**get_db_config())
            cursor = conn.cursor(pymysql.cursors.DictCursor)

        where_clause = ""
        params = []

        if date_from and date_to:
            where_clause = "WHERE dateadm BETWEEN %s AND %s"
            params = [date_from, date_to]

        cursor.execute(f"""
            SELECT
                COUNT(*) as total_records,
                SUM(CASE WHEN his_matched = TRUE THEN 1 ELSE 0 END) as matched,
                SUM(CASE WHEN his_matched = FALSE OR his_matched IS NULL THEN 1 ELSE 0 END) as unmatched
            FROM claim_rep_opip_nhso_item
            {where_clause}
        """, params)

        stats = cursor.fetchone()

        cursor.close()
        conn.close()

        total = int(stats['total_records'] or 0)
        matched = int(stats['matched'] or 0)
        unmatched = int(stats['unmatched'] or 0)
        match_rate = matched / total if total > 0 else 0

        return jsonify({
            'success': True,
            'data': {
                'total_records': total,
                'matched': matched,
                'unmatched': unmatched,
                'match_rate': round(match_rate, 4),
                'last_sync': datetime.now().isoformat() + 'Z'
            }
        })

    except Exception as e:
        logger.error(f"Error getting reconciliation status: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'code': 'INTERNAL_ERROR'
        }), 500


# ==================== Import Status ====================

@external_api_bp.route('/imports/status', methods=['GET'])
@require_api_key
def imports_status():
    """
    Get import status for all file types

    GET /api/v1/imports/status
    """
    try:
        conn = None
        cursor = None

        if DB_TYPE == 'postgresql':
            conn = psycopg2.connect(**get_db_config())
            cursor = conn.cursor(cursor_factory=RealDictCursor)
        else:
            conn = pymysql.connect(**get_db_config())
            cursor = conn.cursor(pymysql.cursors.DictCursor)

        # REP status
        cursor.execute("""
            SELECT
                COUNT(*) as total_files,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as imported,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                MAX(import_completed_at) as last_import
            FROM eclaim_imported_files
            WHERE file_type = 'rep'
        """)
        rep = cursor.fetchone()

        # STM status
        cursor.execute("""
            SELECT
                COUNT(*) as total_files,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as imported,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                MAX(import_completed_at) as last_import
            FROM eclaim_imported_files
            WHERE file_type = 'stm'
        """)
        stm = cursor.fetchone()

        # SMT status (handle table not exists)
        smt = None
        try:
            cursor.execute("""
                SELECT
                    COUNT(*) as total_records,
                    SUM(total) as total_amount,
                    MAX(imported_at) as last_sync
                FROM smt_budget
            """)
            smt = cursor.fetchone()
        except Exception as smt_error:
            logger.warning(f"SMT table not found or error: {smt_error}")
            smt = {'total_records': 0, 'total_amount': 0, 'last_sync': None}

        cursor.close()
        conn.close()

        # Format response
        response = {
            'success': True,
            'data': {
                'rep': {
                    'total_files': int(rep['total_files'] or 0),
                    'imported': int(rep['imported'] or 0),
                    'failed': int(rep['failed'] or 0),
                    'last_import': rep['last_import'].isoformat() + 'Z' if rep['last_import'] else None
                },
                'stm': {
                    'total_files': int(stm['total_files'] or 0),
                    'imported': int(stm['imported'] or 0),
                    'failed': int(stm['failed'] or 0),
                    'last_import': stm['last_import'].isoformat() + 'Z' if stm['last_import'] else None
                },
                'smt': {
                    'total_records': int(smt['total_records'] or 0),
                    'total_amount': float(smt['total_amount'] or 0),
                    'last_sync': smt['last_sync'].strftime('%Y-%m-%d') if smt.get('last_sync') else None
                }
            }
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error getting imports status: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'code': 'INTERNAL_ERROR'
        }), 500


# ==================== Error Handler ====================

@external_api_bp.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        'success': False,
        'error': 'Endpoint not found',
        'code': 'NOT_FOUND'
    }), 404


@external_api_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({
        'success': False,
        'error': 'Internal server error',
        'code': 'INTERNAL_ERROR'
    }), 500
