"""
System API Blueprint
Handles system health checks, seed data initialization, and status synchronization
"""

import os
import logging
import json
import subprocess
import re
import threading
from datetime import datetime
from pathlib import Path
from flask import Blueprint, jsonify, current_app
from zoneinfo import ZoneInfo
import psutil

from config.database import DOWNLOADS_DIR, DB_TYPE
from config.db_pool import get_connection as get_pooled_connection, return_connection
from utils.logging_config import setup_logger, safe_format_exception
from utils.job_history_manager import job_history_manager

# Setup logger
logger = setup_logger('system_api', logging.INFO, 'logs/system_api.log')

# Create blueprint
system_api_bp = Blueprint('system_api', __name__)

# Timezone
TZ_BANGKOK = ZoneInfo('Asia/Bangkok')

# Global progress tracking for seed initialization
seed_progress = {
    'running': False,
    'current_task': None,
    'tasks': [],
    'completed': 0,
    'total': 0,
    'error': None
}


def get_db_connection():
    """Get database connection from pool"""
    try:
        conn = get_pooled_connection()
        if conn is None:
            logger.error("Failed to get connection from pool")
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None


def _check_pid_alive(pid_file_path):
    """Helper to check if PID in file is alive"""
    try:
        pid_file = Path(pid_file_path)
        if not pid_file.exists():
            return False
        pid = int(pid_file.read_text().strip())
        process = psutil.Process(pid)
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except (ValueError, IOError, psutil.NoSuchProcess):
        return False


# ==================== System Health Dashboard ====================

@system_api_bp.route('/api/system/health')
def get_system_health():
    """
    Comprehensive system health dashboard
    Returns status of all system components
    """
    health = {
        'success': True,
        'timestamp': datetime.now(TZ_BANGKOK).isoformat(),
        'overall_status': 'healthy',  # healthy, warning, critical
        'components': {}
    }

    issues = []

    # === 1. Database Connection ===
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")

            # Get database type
            db_type_display = 'PostgreSQL' if DB_TYPE == 'postgresql' else 'MySQL'

            cursor.close()
            conn.close()

            health['components']['database'] = {
                'status': 'healthy',
                'message': 'Connected',
                'type': db_type_display
            }
        else:
            health['components']['database'] = {
                'status': 'critical',
                'message': 'Cannot connect to database'
            }
            issues.append('database')
    except Exception as e:
        health['components']['database'] = {
            'status': 'critical',
            'message': f'Database error: {str(e)}'
        }
        issues.append('database')

    # === 2. Disk Space ===
    try:
        downloads_dir = Path(DOWNLOADS_DIR)
        if downloads_dir.exists():
            import shutil
            disk = shutil.disk_usage(str(downloads_dir))
            free_gb = disk.free / (1024**3)
            total_gb = disk.total / (1024**3)
            used_percent = (disk.used / disk.total) * 100

            disk_status = 'healthy'
            if used_percent > 90:
                disk_status = 'critical'
                issues.append('disk')
            elif used_percent > 80:
                disk_status = 'warning'

            health['components']['disk'] = {
                'status': disk_status,
                'free_gb': round(free_gb, 2),
                'total_gb': round(total_gb, 2),
                'used_percent': round(used_percent, 1),
                'message': f'{round(free_gb, 1)} GB free ({round(100-used_percent, 1)}%)'
            }
        else:
            health['components']['disk'] = {
                'status': 'warning',
                'message': 'Downloads directory not found'
            }
    except Exception as e:
        health['components']['disk'] = {
            'status': 'warning',
            'message': f'Cannot check disk: {str(e)}'
        }

    # === 3. Running Processes ===
    pid_files = {
        'downloader': Path('/tmp/eclaim_downloader.pid'),
        'import': Path('/tmp/eclaim_import.pid'),
        'parallel': Path('/tmp/eclaim_parallel_download.pid'),
        'stm': Path('/tmp/eclaim_stm_downloader.pid'),
        'smt': Path('/tmp/eclaim_smt_fetch.pid')
    }

    running_processes = []
    stale_processes = []

    for name, pid_file in pid_files.items():
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                if psutil.pid_exists(pid):
                    proc = psutil.Process(pid)
                    running_processes.append({
                        'name': name,
                        'pid': pid,
                        'status': proc.status(),
                        'started': datetime.fromtimestamp(proc.create_time()).isoformat()
                    })
                else:
                    stale_processes.append(name)
            except (ValueError, psutil.NoSuchProcess):
                stale_processes.append(name)

    process_status = 'healthy'
    if stale_processes:
        process_status = 'warning'

    health['components']['processes'] = {
        'status': process_status,
        'running': running_processes,
        'running_count': len(running_processes),
        'stale_pids': stale_processes,
        'message': f'{len(running_processes)} active' + (f', {len(stale_processes)} stale PIDs' if stale_processes else '')
    }

    # === 4. Recent Jobs (last 24 hours) ===
    try:
        recent_jobs = job_history_manager.get_recent_jobs(limit=100)
        now = datetime.now()

        jobs_24h = {
            'total': 0,
            'running': 0,
            'completed': 0,
            'failed': 0
        }

        for job in recent_jobs:
            try:
                started = datetime.fromisoformat(job['started_at'].replace('Z', '+00:00')) if isinstance(job['started_at'], str) else job['started_at']
                if started.tzinfo:
                    started = started.replace(tzinfo=None)
                if (now - started).total_seconds() < 86400:  # 24 hours
                    jobs_24h['total'] += 1
                    if job['status'] == 'running':
                        jobs_24h['running'] += 1
                    elif job['status'] in ('completed', 'completed_with_errors'):
                        jobs_24h['completed'] += 1
                    elif job['status'] == 'failed':
                        jobs_24h['failed'] += 1
            except (ValueError, TypeError):
                pass

        jobs_status = 'healthy'
        if jobs_24h['failed'] > jobs_24h['completed']:
            jobs_status = 'critical'
            issues.append('jobs')
        elif jobs_24h['failed'] > 0:
            jobs_status = 'warning'

        health['components']['jobs'] = {
            'status': jobs_status,
            'last_24h': jobs_24h,
            'message': f"{jobs_24h['completed']} completed, {jobs_24h['failed']} failed in 24h"
        }
    except Exception as e:
        health['components']['jobs'] = {
            'status': 'warning',
            'message': f'Cannot check jobs: {str(e)}'
        }

    # === 5. Files Statistics ===
    try:
        downloads_dir = Path(DOWNLOADS_DIR)
        if downloads_dir.exists():
            # Search recursively in subdirectories (rep/, stm/, smt/)
            xls_files = list(downloads_dir.glob('**/*.xls'))
            total_size = sum(f.stat().st_size for f in xls_files if f.exists())

            health['components']['files'] = {
                'status': 'healthy',
                'count': len(xls_files),
                'total_size_mb': round(total_size / (1024**2), 2),
                'message': f'{len(xls_files)} files ({round(total_size / (1024**2), 1)} MB)'
            }
        else:
            health['components']['files'] = {
                'status': 'warning',
                'count': 0,
                'message': 'Downloads directory not found'
            }
    except Exception as e:
        health['components']['files'] = {
            'status': 'warning',
            'message': f'Cannot check files: {str(e)}'
        }

    # === 6. Memory Usage ===
    try:
        memory = psutil.virtual_memory()
        mem_status = 'healthy'
        if memory.percent > 90:
            mem_status = 'critical'
            issues.append('memory')
        elif memory.percent > 80:
            mem_status = 'warning'

        health['components']['memory'] = {
            'status': mem_status,
            'used_percent': round(memory.percent, 1),
            'available_gb': round(memory.available / (1024**3), 2),
            'message': f'{round(memory.percent, 1)}% used, {round(memory.available / (1024**3), 1)} GB available'
        }
    except Exception as e:
        health['components']['memory'] = {
            'status': 'warning',
            'message': f'Cannot check memory: {str(e)}'
        }

    # === Determine Overall Status ===
    if 'database' in issues or 'memory' in issues:
        health['overall_status'] = 'critical'
    elif 'disk' in issues or 'jobs' in issues:
        health['overall_status'] = 'warning'
    elif any(c.get('status') == 'warning' for c in health['components'].values()):
        health['overall_status'] = 'warning'

    health['issues'] = issues

    return jsonify(health)


# ==================== Seed Data Initialization ====================

@system_api_bp.route('/api/system/seed-status')
def get_seed_status():
    """
    Check if seed data initialization is needed.
    Returns status of each seed data table.
    """
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Check each seed table
        seed_tables = {
            'dim_date': {'name': 'Dimension Date', 'min_records': 100},
            'health_offices': {'name': 'Health Offices', 'min_records': 1000},
            'nhso_error_codes': {'name': 'NHSO Error Codes', 'min_records': 10},
            'fund_types': {'name': 'Fund Types', 'min_records': 5},
            'service_types': {'name': 'Service Types', 'min_records': 5}
        }

        results = {}
        needs_init = False

        for table, info in seed_tables.items():
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                is_empty = count < info['min_records']
                results[table] = {
                    'name': info['name'],
                    'count': count,
                    'is_empty': is_empty,
                    'min_required': info['min_records']
                }
                if is_empty:
                    needs_init = True
            except Exception as e:
                results[table] = {
                    'name': info['name'],
                    'count': 0,
                    'is_empty': True,
                    'error': str(e)
                }
                needs_init = True

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'needs_initialization': needs_init,
            'tables': results,
            'seed_running': seed_progress['running'],
            'seed_progress': seed_progress if seed_progress['running'] else None
        })

    except Exception as e:
        logger.error(safe_format_exception())
        return jsonify({'success': False, 'error': str(e)}), 500


@system_api_bp.route('/api/system/seed-init', methods=['POST'])
def run_seed_initialization():
    """
    Start seed data initialization process.
    Runs in background and updates progress.
    """
    global seed_progress

    if seed_progress['running']:
        return jsonify({
            'success': False,
            'error': 'Seed initialization already running',
            'progress': seed_progress
        }), 400

    # Start seed process in background thread
    def run_seeds():
        global seed_progress
        seed_progress = {
            'running': True,
            'current_task': None,
            'tasks': [
                {'id': 'dim', 'name': 'Dimension Tables', 'status': 'pending', 'records': 0},
                {'id': 'health', 'name': 'Health Offices', 'status': 'pending', 'records': 0},
                {'id': 'errors', 'name': 'NHSO Error Codes', 'status': 'pending', 'records': 0}
            ],
            'completed': 0,
            'total': 3,
            'error': None,
            'started_at': datetime.now(TZ_BANGKOK).isoformat()
        }

        try:
            # Task 1: Dimension tables (migrate.py --seed)
            seed_progress['current_task'] = 'dim'
            seed_progress['tasks'][0]['status'] = 'running'

            # Get app root directory (container: /app, local: project root)
            cwd = os.environ.get('APP_ROOT', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            result = subprocess.run(
                ['python', 'database/migrate.py', '--seed'],
                capture_output=True,
                text=True,
                cwd=cwd
            )
            if result.returncode != 0:
                raise Exception(f"Dimension seed failed: {result.stderr}")

            seed_progress['tasks'][0]['status'] = 'completed'
            seed_progress['tasks'][0]['records'] = 2600  # Approximate
            seed_progress['completed'] = 1

            # Task 2: Health Offices
            seed_progress['current_task'] = 'health'
            seed_progress['tasks'][1]['status'] = 'running'

            result = subprocess.run(
                ['python', 'database/seeds/health_offices_importer.py'],
                capture_output=True,
                text=True,
                cwd=cwd
            )
            if result.returncode != 0:
                raise Exception(f"Health offices seed failed: {result.stderr}")

            # Parse record count from output
            match = re.search(r'Imported: (\d+)', result.stdout)
            records = int(match.group(1)) if match else 43884

            seed_progress['tasks'][1]['status'] = 'completed'
            seed_progress['tasks'][1]['records'] = records
            seed_progress['completed'] = 2

            # Task 3: NHSO Error Codes
            seed_progress['current_task'] = 'errors'
            seed_progress['tasks'][2]['status'] = 'running'

            # Pass the correct path to the error codes SQL file
            sql_file = os.path.join(cwd, 'database/seeds/nhso_error_codes.sql')
            result = subprocess.run(
                ['python', 'database/seeds/nhso_error_codes_importer.py', sql_file],
                capture_output=True,
                text=True,
                cwd=cwd
            )
            if result.returncode != 0:
                raise Exception(f"Error codes seed failed: {result.stderr}")

            # Parse record count from output
            match = re.search(r'Imported[:\s]+(\d+)', result.stdout)
            records = int(match.group(1)) if match else 0

            seed_progress['tasks'][2]['status'] = 'completed'
            seed_progress['tasks'][2]['records'] = records
            seed_progress['completed'] = 3

            seed_progress['current_task'] = None
            seed_progress['finished_at'] = datetime.now(TZ_BANGKOK).isoformat()

        except Exception as e:
            seed_progress['error'] = str(e)
            # Mark current task as failed
            for task in seed_progress['tasks']:
                if task['status'] == 'running':
                    task['status'] = 'failed'
                    task['error'] = str(e)

        finally:
            seed_progress['running'] = False

    thread = threading.Thread(target=run_seeds, daemon=True)
    thread.start()

    return jsonify({
        'success': True,
        'message': 'Seed initialization started',
        'progress': seed_progress
    })


@system_api_bp.route('/api/system/seed-progress')
def get_seed_progress():
    """Get current seed initialization progress"""
    return jsonify({
        'success': True,
        'progress': seed_progress
    })


@system_api_bp.route('/api/system/sync-status', methods=['POST'])
def sync_system_status():
    """
    Comprehensive system status check and sync:
    1. Check if download processes are actually running
    2. Reset stuck progress files if processes are dead
    3. Sync files in folders with history records
    4. Return detailed status report
    """
    report = {
        'success': True,
        'timestamp': datetime.now(TZ_BANGKOK).isoformat(),
        'actions': [],
        'summary': {
            'processes_checked': 0,
            'processes_reset': 0,
            'files_synced': 0,
            'files_added': 0,
            'files_removed': 0
        }
    }

    # PID files to check
    pid_files = {
        'downloader': Path('/tmp/eclaim_downloader.pid'),
        'import': Path('/tmp/eclaim_import.pid'),
        'parallel': Path('/tmp/eclaim_parallel_download.pid'),
        'stm': Path('/tmp/eclaim_stm_downloader.pid'),
        'smt': Path('/tmp/eclaim_smt_fetch.pid')
    }

    # === STEP 1: Check PID files and reset if processes are dead ===
    for name, pid_file in pid_files.items():
        report['summary']['processes_checked'] += 1
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                try:
                    process = psutil.Process(pid)
                    if process.is_running() and process.status() != psutil.STATUS_ZOMBIE:
                        report['actions'].append({
                            'type': 'process_check',
                            'name': name,
                            'pid': pid,
                            'status': 'running',
                            'action': 'none'
                        })
                    else:
                        # Process is zombie, cleanup
                        pid_file.unlink()
                        report['actions'].append({
                            'type': 'process_check',
                            'name': name,
                            'pid': pid,
                            'status': 'zombie',
                            'action': 'pid_file_removed'
                        })
                        report['summary']['processes_reset'] += 1
                except psutil.NoSuchProcess:
                    # Process doesn't exist, cleanup
                    pid_file.unlink()
                    report['actions'].append({
                        'type': 'process_check',
                        'name': name,
                        'pid': pid,
                        'status': 'dead',
                        'action': 'pid_file_removed'
                    })
                    report['summary']['processes_reset'] += 1
            except (ValueError, IOError) as e:
                pid_file.unlink()
                report['actions'].append({
                    'type': 'process_check',
                    'name': name,
                    'status': 'invalid_pid_file',
                    'action': 'pid_file_removed',
                    'error': str(e)
                })
                report['summary']['processes_reset'] += 1

    # === STEP 2: Sync REP files with database ===
    # (Progress tracking now uses database - no JSON files to reset)
    # REP files are stored in downloads/rep/ subfolder
    rep_dir = Path('downloads/rep')

    if rep_dir.exists():
        try:
            conn = get_pooled_connection()
            cursor = conn.cursor()

            # Get existing filenames in database
            cursor.execute("SELECT filename FROM download_history WHERE download_type = 'rep'")
            db_filenames = {row[0] for row in cursor.fetchall()}

            # Get actual files on disk
            disk_files = {f.name for f in rep_dir.glob('*.xls') if f.is_file() and f.stat().st_size > 0}

            # Files on disk but not in database -> add to database
            missing_from_db = disk_files - db_filenames
            db_type = os.environ.get('DB_TYPE', 'postgresql').lower()
            for filename in missing_from_db:
                file_path = rep_dir / filename
                if db_type == 'mysql':
                    cursor.execute("""
                        INSERT INTO download_history
                        (download_type, filename, file_size, file_path, file_exists)
                        VALUES ('rep', %s, %s, %s, TRUE)
                        ON DUPLICATE KEY UPDATE file_size = VALUES(file_size)
                    """, (filename, file_path.stat().st_size, str(file_path)))
                else:
                    cursor.execute("""
                        INSERT INTO download_history
                        (download_type, filename, file_size, file_path, file_exists)
                        VALUES ('rep', %s, %s, %s, TRUE)
                        ON CONFLICT (download_type, filename) DO NOTHING
                    """, (filename, file_path.stat().st_size, str(file_path)))
                report['summary']['files_added'] += 1

            # Files in database but not on disk -> mark as file_exists=FALSE
            missing_from_disk = db_filenames - disk_files
            if missing_from_disk:
                for filename in missing_from_disk:
                    cursor.execute("""
                        UPDATE download_history
                        SET file_exists = FALSE, updated_at = CURRENT_TIMESTAMP
                        WHERE download_type = 'rep' AND filename = %s
                    """, (filename,))
                report['summary']['files_removed'] += len(missing_from_disk)

            conn.commit()
            cursor.close()
            return_connection(conn)

            if missing_from_db or missing_from_disk:
                report['actions'].append({
                    'type': 'history_sync',
                    'target': 'REP files (database)',
                    'added': len(missing_from_db),
                    'removed': len(missing_from_disk)
                })

            report['summary']['files_synced'] = len(disk_files)

        except Exception as e:
            report['actions'].append({
                'type': 'history_sync',
                'target': 'REP files',
                'status': 'error',
                'error': str(e)
            })

    # === STEP 4: Sync Statement files with database ===
    # Statement files are stored in downloads/stm/ subfolder
    stm_dir = Path('downloads/stm')

    if stm_dir.exists():
        try:
            conn = get_pooled_connection()
            cursor = conn.cursor()

            # Get existing filenames in database
            cursor.execute("SELECT filename FROM download_history WHERE download_type = 'stm'")
            stm_db_filenames = {row[0] for row in cursor.fetchall()}

            # Get actual files on disk
            stm_disk_files = {f.name for f in stm_dir.glob('*.xls') if f.is_file() and f.stat().st_size > 0}

            # Files on disk but not in database -> add to database
            stm_missing_from_db = stm_disk_files - stm_db_filenames
            db_type = os.environ.get('DB_TYPE', 'postgresql').lower()
            for filename in stm_missing_from_db:
                file_path = stm_dir / filename
                if db_type == 'mysql':
                    cursor.execute("""
                        INSERT INTO download_history
                        (download_type, filename, file_size, file_path, file_exists)
                        VALUES ('stm', %s, %s, %s, TRUE)
                        ON DUPLICATE KEY UPDATE file_size = VALUES(file_size)
                    """, (filename, file_path.stat().st_size, str(file_path)))
                else:
                    cursor.execute("""
                        INSERT INTO download_history
                        (download_type, filename, file_size, file_path, file_exists)
                        VALUES ('stm', %s, %s, %s, TRUE)
                        ON CONFLICT (download_type, filename) DO NOTHING
                    """, (filename, file_path.stat().st_size, str(file_path)))
                report['summary']['files_added'] += 1

            # Files in database but not on disk -> mark as file_exists=FALSE
            stm_missing_from_disk = stm_db_filenames - stm_disk_files
            if stm_missing_from_disk:
                for filename in stm_missing_from_disk:
                    cursor.execute("""
                        UPDATE download_history
                        SET file_exists = FALSE, updated_at = CURRENT_TIMESTAMP
                        WHERE download_type = 'stm' AND filename = %s
                    """, (filename,))
                report['summary']['files_removed'] += len(stm_missing_from_disk)

            conn.commit()
            cursor.close()
            return_connection(conn)

            if stm_missing_from_db or stm_missing_from_disk:
                report['actions'].append({
                    'type': 'history_sync',
                    'target': 'Statement files (database)',
                    'added': len(stm_missing_from_db),
                    'removed': len(stm_missing_from_disk)
                })

        except Exception as e:
            report['actions'].append({
                'type': 'history_sync',
                'target': 'Statement files',
                'status': 'error',
                'error': str(e)
            })

    # Generate summary message
    actions_taken = report['summary']['processes_reset'] + report['summary']['files_added'] + report['summary']['files_removed']
    if actions_taken > 0:
        report['message'] = f"Sync completed: Reset {report['summary']['processes_reset']} processes, " \
                           f"Added {report['summary']['files_added']} files, " \
                           f"Removed {report['summary']['files_removed']} orphaned records"
    else:
        report['message'] = "All systems are in sync. No actions needed."

    return jsonify(report), 200
