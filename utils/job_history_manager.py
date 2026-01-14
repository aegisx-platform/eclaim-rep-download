#!/usr/bin/env python3
"""
Job History Manager - Track and manage job execution history
"""

import json
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

from config.db_pool import get_db_connection
from config.database import DB_TYPE


class JobHistoryManager:
    """Manage job history records in database"""

    def __init__(self):
        self._ensure_table_exists()

    def _ensure_table_exists(self):
        """Create job_history table if not exists"""
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            if DB_TYPE == 'mysql':
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS job_history (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        job_id VARCHAR(100) NOT NULL UNIQUE,
                        job_type VARCHAR(50) NOT NULL,
                        job_subtype VARCHAR(50),
                        status VARCHAR(20) NOT NULL DEFAULT 'running',
                        started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP NULL,
                        duration_seconds INT,
                        parameters JSON,
                        results JSON,
                        error_message TEXT,
                        triggered_by VARCHAR(50) DEFAULT 'manual',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        INDEX idx_job_type (job_type),
                        INDEX idx_job_status (status),
                        INDEX idx_job_started (started_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS job_history (
                        id SERIAL PRIMARY KEY,
                        job_id VARCHAR(100) NOT NULL UNIQUE,
                        job_type VARCHAR(50) NOT NULL,
                        job_subtype VARCHAR(50),
                        status VARCHAR(20) NOT NULL DEFAULT 'running',
                        started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP,
                        duration_seconds INTEGER,
                        parameters JSONB,
                        results JSONB,
                        error_message TEXT,
                        triggered_by VARCHAR(50) DEFAULT 'manual',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # Create indexes
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_history_type ON job_history(job_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_history_status ON job_history(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_history_started ON job_history(started_at DESC)")

            conn.commit()
            cursor.close()
            conn.close()

        except Exception as e:
            print(f"Error ensuring job_history table: {e}")

    def start_job(
        self,
        job_type: str,
        job_subtype: str = None,
        parameters: Dict = None,
        triggered_by: str = 'manual'
    ) -> str:
        """
        Record start of a new job

        Args:
            job_type: Type of job (download, import, schedule)
            job_subtype: Subtype (single, bulk, parallel)
            parameters: Job parameters dict
            triggered_by: Who triggered (manual, schedule, api)

        Returns:
            job_id string
        """
        job_id = f"{job_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        try:
            conn = get_db_connection()
            if not conn:
                return job_id

            cursor = conn.cursor()

            params_json = json.dumps(parameters) if parameters else None

            if DB_TYPE == 'mysql':
                cursor.execute("""
                    INSERT INTO job_history (job_id, job_type, job_subtype, status, parameters, triggered_by)
                    VALUES (%s, %s, %s, 'running', %s, %s)
                """, (job_id, job_type, job_subtype, params_json, triggered_by))
            else:
                cursor.execute("""
                    INSERT INTO job_history (job_id, job_type, job_subtype, status, parameters, triggered_by)
                    VALUES (%s, %s, %s, 'running', %s, %s)
                """, (job_id, job_type, job_subtype, params_json, triggered_by))

            conn.commit()
            cursor.close()
            conn.close()

        except Exception as e:
            print(f"Error starting job: {e}")

        return job_id

    def complete_job(
        self,
        job_id: str,
        status: str = 'completed',
        results: Dict = None,
        error_message: str = None
    ):
        """
        Record job completion

        Args:
            job_id: Job identifier
            status: Final status (completed, failed, cancelled)
            results: Results dict
            error_message: Error message if failed
        """
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            completed_at = datetime.now()
            results_json = json.dumps(results) if results else None

            # Calculate duration
            if DB_TYPE == 'mysql':
                cursor.execute("""
                    UPDATE job_history SET
                        status = %s,
                        completed_at = %s,
                        duration_seconds = TIMESTAMPDIFF(SECOND, started_at, %s),
                        results = %s,
                        error_message = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE job_id = %s
                """, (status, completed_at, completed_at, results_json, error_message, job_id))
            else:
                cursor.execute("""
                    UPDATE job_history SET
                        status = %s,
                        completed_at = %s,
                        duration_seconds = EXTRACT(EPOCH FROM (%s - started_at))::INTEGER,
                        results = %s,
                        error_message = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE job_id = %s
                """, (status, completed_at, completed_at, results_json, error_message, job_id))

            conn.commit()
            cursor.close()
            conn.close()

        except Exception as e:
            print(f"Error completing job: {e}")

    def update_job_progress(self, job_id: str, results: Dict):
        """Update job results during execution"""
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            results_json = json.dumps(results) if results else None

            cursor.execute("""
                UPDATE job_history SET
                    results = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE job_id = %s
            """, (results_json, job_id))

            conn.commit()
            cursor.close()
            conn.close()

        except Exception as e:
            print(f"Error updating job progress: {e}")

    def get_recent_jobs(
        self,
        job_type: str = None,
        status: str = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get recent jobs

        Args:
            job_type: Filter by type
            status: Filter by status
            limit: Max records to return

        Returns:
            List of job records
        """
        try:
            conn = get_db_connection()
            if not conn:
                return []

            cursor = conn.cursor()

            query = "SELECT * FROM job_history WHERE 1=1"
            params = []

            if job_type:
                query += " AND job_type = %s"
                params.append(job_type)

            if status:
                query += " AND status = %s"
                params.append(status)

            query += " ORDER BY started_at DESC LIMIT %s"
            params.append(limit)

            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

            cursor.close()
            conn.close()

            jobs = []
            for row in rows:
                job = dict(zip(columns, row))
                # Parse JSON fields
                if job.get('parameters'):
                    if isinstance(job['parameters'], str):
                        job['parameters'] = json.loads(job['parameters'])
                if job.get('results'):
                    if isinstance(job['results'], str):
                        job['results'] = json.loads(job['results'])
                # Convert datetime to ISO string
                for key in ['started_at', 'completed_at', 'created_at', 'updated_at']:
                    if job.get(key) and hasattr(job[key], 'isoformat'):
                        job[key] = job[key].isoformat()
                jobs.append(job)

            return jobs

        except Exception as e:
            print(f"Error getting recent jobs: {e}")
            return []

    def get_job_stats(self, days: int = 7) -> Dict:
        """
        Get job statistics for the last N days

        Args:
            days: Number of days to look back

        Returns:
            Statistics dict
        """
        try:
            conn = get_db_connection()
            if not conn:
                return {}

            cursor = conn.cursor()

            if DB_TYPE == 'mysql':
                date_filter = f"started_at >= DATE_SUB(NOW(), INTERVAL {days} DAY)"
            else:
                date_filter = f"started_at >= NOW() - INTERVAL '{days} days'"

            cursor.execute(f"""
                SELECT
                    job_type,
                    status,
                    COUNT(*) as count,
                    AVG(duration_seconds) as avg_duration
                FROM job_history
                WHERE {date_filter}
                GROUP BY job_type, status
            """)

            rows = cursor.fetchall()
            cursor.close()
            conn.close()

            stats = {
                'by_type': {},
                'by_status': {},
                'total': 0
            }

            for row in rows:
                job_type, status, count, avg_duration = row

                if job_type not in stats['by_type']:
                    stats['by_type'][job_type] = {'total': 0, 'completed': 0, 'failed': 0}
                stats['by_type'][job_type]['total'] += count
                stats['by_type'][job_type][status] = count
                stats['by_type'][job_type]['avg_duration'] = round(avg_duration or 0)

                if status not in stats['by_status']:
                    stats['by_status'][status] = 0
                stats['by_status'][status] += count

                stats['total'] += count

            return stats

        except Exception as e:
            print(f"Error getting job stats: {e}")
            return {}


# Global instance
job_history_manager = JobHistoryManager()
