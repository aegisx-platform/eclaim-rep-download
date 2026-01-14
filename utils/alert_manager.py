#!/usr/bin/env python3
"""
Alert Manager - System alerts and notifications
"""

import json
from datetime import datetime
from typing import Dict, List, Optional

from config.db_pool import get_db_connection
from config.database import DB_TYPE


class AlertManager:
    """Manage system alerts and notifications"""

    # Alert types
    TYPE_JOB_FAILED = 'job_failed'
    TYPE_DISK_WARNING = 'disk_warning'
    TYPE_MEMORY_WARNING = 'memory_warning'
    TYPE_STALE_PROCESS = 'stale_process'
    TYPE_DB_ERROR = 'db_error'
    TYPE_IMPORT_ERROR = 'import_error'

    # Severity levels
    SEVERITY_INFO = 'info'
    SEVERITY_WARNING = 'warning'
    SEVERITY_CRITICAL = 'critical'

    def __init__(self):
        self._ensure_table_exists()

    def _ensure_table_exists(self):
        """Create alerts table if not exists"""
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            if DB_TYPE == 'mysql':
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS system_alerts (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        alert_type VARCHAR(50) NOT NULL,
                        severity VARCHAR(20) NOT NULL,
                        title VARCHAR(255) NOT NULL,
                        message TEXT,
                        related_type VARCHAR(50),
                        related_id VARCHAR(100),
                        is_read BOOLEAN DEFAULT FALSE,
                        is_dismissed BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        read_at TIMESTAMP NULL,
                        dismissed_at TIMESTAMP NULL,
                        INDEX idx_alerts_type (alert_type),
                        INDEX idx_alerts_unread (is_read, is_dismissed),
                        INDEX idx_alerts_created (created_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS system_alerts (
                        id SERIAL PRIMARY KEY,
                        alert_type VARCHAR(50) NOT NULL,
                        severity VARCHAR(20) NOT NULL,
                        title VARCHAR(255) NOT NULL,
                        message TEXT,
                        related_type VARCHAR(50),
                        related_id VARCHAR(100),
                        is_read BOOLEAN DEFAULT FALSE,
                        is_dismissed BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        read_at TIMESTAMP,
                        dismissed_at TIMESTAMP
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_type ON system_alerts(alert_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_unread ON system_alerts(is_read, is_dismissed)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_created ON system_alerts(created_at DESC)")

            conn.commit()
            cursor.close()
            conn.close()

        except Exception as e:
            print(f"Error ensuring alerts table: {e}")

    def create_alert(
        self,
        alert_type: str,
        severity: str,
        title: str,
        message: str = None,
        related_type: str = None,
        related_id: str = None
    ) -> Optional[int]:
        """
        Create a new alert

        Args:
            alert_type: Type of alert
            severity: Severity level (info, warning, critical)
            title: Alert title
            message: Detailed message
            related_type: Related entity type (job, process, system)
            related_id: Related entity ID

        Returns:
            Alert ID or None if failed
        """
        try:
            conn = get_db_connection()
            if not conn:
                return None

            cursor = conn.cursor()

            if DB_TYPE == 'mysql':
                cursor.execute("""
                    INSERT INTO system_alerts
                    (alert_type, severity, title, message, related_type, related_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (alert_type, severity, title, message, related_type, related_id))
                alert_id = cursor.lastrowid
            else:
                cursor.execute("""
                    INSERT INTO system_alerts
                    (alert_type, severity, title, message, related_type, related_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (alert_type, severity, title, message, related_type, related_id))
                result = cursor.fetchone()
                alert_id = result[0] if result else None

            conn.commit()
            cursor.close()
            conn.close()

            return alert_id

        except Exception as e:
            print(f"Error creating alert: {e}")
            return None

    def get_unread_count(self) -> int:
        """Get count of unread, not dismissed alerts"""
        try:
            conn = get_db_connection()
            if not conn:
                return 0

            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM system_alerts
                WHERE is_read = FALSE AND is_dismissed = FALSE
            """)
            result = cursor.fetchone()
            cursor.close()
            conn.close()

            return result[0] if result else 0

        except Exception as e:
            print(f"Error getting unread count: {e}")
            return 0

    def get_alerts(
        self,
        include_dismissed: bool = False,
        alert_type: str = None,
        severity: str = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get alerts list

        Args:
            include_dismissed: Include dismissed alerts
            alert_type: Filter by type
            severity: Filter by severity
            limit: Max records

        Returns:
            List of alert dicts
        """
        try:
            conn = get_db_connection()
            if not conn:
                return []

            cursor = conn.cursor()

            query = "SELECT * FROM system_alerts WHERE 1=1"
            params = []

            if not include_dismissed:
                query += " AND is_dismissed = FALSE"

            if alert_type:
                query += " AND alert_type = %s"
                params.append(alert_type)

            if severity:
                query += " AND severity = %s"
                params.append(severity)

            query += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)

            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

            cursor.close()
            conn.close()

            alerts = []
            for row in rows:
                alert = dict(zip(columns, row))
                # Convert datetime to ISO string
                for key in ['created_at', 'read_at', 'dismissed_at']:
                    if alert.get(key) and hasattr(alert[key], 'isoformat'):
                        alert[key] = alert[key].isoformat()
                alerts.append(alert)

            return alerts

        except Exception as e:
            print(f"Error getting alerts: {e}")
            return []

    def mark_as_read(self, alert_id: int) -> bool:
        """Mark an alert as read"""
        try:
            conn = get_db_connection()
            if not conn:
                return False

            cursor = conn.cursor()
            cursor.execute("""
                UPDATE system_alerts
                SET is_read = TRUE, read_at = %s
                WHERE id = %s
            """, (datetime.now(), alert_id))

            conn.commit()
            cursor.close()
            conn.close()

            return True

        except Exception as e:
            print(f"Error marking alert as read: {e}")
            return False

    def mark_all_as_read(self) -> int:
        """Mark all unread alerts as read"""
        try:
            conn = get_db_connection()
            if not conn:
                return 0

            cursor = conn.cursor()
            cursor.execute("""
                UPDATE system_alerts
                SET is_read = TRUE, read_at = %s
                WHERE is_read = FALSE
            """, (datetime.now(),))

            affected = cursor.rowcount
            conn.commit()
            cursor.close()
            conn.close()

            return affected

        except Exception as e:
            print(f"Error marking all as read: {e}")
            return 0

    def dismiss_alert(self, alert_id: int) -> bool:
        """Dismiss an alert"""
        try:
            conn = get_db_connection()
            if not conn:
                return False

            cursor = conn.cursor()
            cursor.execute("""
                UPDATE system_alerts
                SET is_dismissed = TRUE, dismissed_at = %s
                WHERE id = %s
            """, (datetime.now(), alert_id))

            conn.commit()
            cursor.close()
            conn.close()

            return True

        except Exception as e:
            print(f"Error dismissing alert: {e}")
            return False

    def dismiss_all(self) -> int:
        """Dismiss all alerts"""
        try:
            conn = get_db_connection()
            if not conn:
                return 0

            cursor = conn.cursor()
            cursor.execute("""
                UPDATE system_alerts
                SET is_dismissed = TRUE, dismissed_at = %s
                WHERE is_dismissed = FALSE
            """, (datetime.now(),))

            affected = cursor.rowcount
            conn.commit()
            cursor.close()
            conn.close()

            return affected

        except Exception as e:
            print(f"Error dismissing all: {e}")
            return 0

    # Convenience methods for creating specific alerts
    def alert_job_failed(self, job_id: str, job_type: str, error: str):
        """Create alert for failed job"""
        return self.create_alert(
            alert_type=self.TYPE_JOB_FAILED,
            severity=self.SEVERITY_CRITICAL,
            title=f"{job_type.title()} job failed",
            message=error,
            related_type='job',
            related_id=job_id
        )

    def alert_disk_warning(self, used_percent: float, free_gb: float):
        """Create alert for disk space warning"""
        severity = self.SEVERITY_CRITICAL if used_percent > 90 else self.SEVERITY_WARNING
        return self.create_alert(
            alert_type=self.TYPE_DISK_WARNING,
            severity=severity,
            title=f"Disk space {'critical' if used_percent > 90 else 'warning'}",
            message=f"Disk usage: {used_percent:.1f}%, {free_gb:.1f} GB free",
            related_type='system'
        )

    def alert_memory_warning(self, used_percent: float, available_gb: float):
        """Create alert for memory warning"""
        severity = self.SEVERITY_CRITICAL if used_percent > 90 else self.SEVERITY_WARNING
        return self.create_alert(
            alert_type=self.TYPE_MEMORY_WARNING,
            severity=severity,
            title=f"Memory {'critical' if used_percent > 90 else 'warning'}",
            message=f"Memory usage: {used_percent:.1f}%, {available_gb:.1f} GB available",
            related_type='system'
        )

    def alert_stale_process(self, process_names: List[str]):
        """Create alert for stale processes"""
        return self.create_alert(
            alert_type=self.TYPE_STALE_PROCESS,
            severity=self.SEVERITY_WARNING,
            title="Stale processes detected",
            message=f"Processes with stale PIDs: {', '.join(process_names)}",
            related_type='system'
        )

    def alert_import_error(self, filename: str, error: str):
        """Create alert for import error"""
        return self.create_alert(
            alert_type=self.TYPE_IMPORT_ERROR,
            severity=self.SEVERITY_CRITICAL,
            title=f"Import failed: {filename}",
            message=error,
            related_type='file',
            related_id=filename
        )


# Global instance
alert_manager = AlertManager()
