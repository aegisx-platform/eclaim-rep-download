#!/usr/bin/env python3
"""
Log Stream Manager - Real-time log streaming via Server-Sent Events (SSE)
"""

import time
import json
from pathlib import Path
from datetime import datetime
from typing import Generator, Optional
import threading


class LogStreamer:
    """Manage real-time log streaming"""

    def __init__(self):
        self.log_file = Path('logs/realtime.log')
        self.log_file.parent.mkdir(exist_ok=True)
        self._lock = threading.Lock()

    def write_log(self, message: str, level: str = 'info', source: str = 'system'):
        """
        Write log entry to file

        Args:
            message: Log message
            level: Log level (info, success, error, warning)
            source: Source of log (download, import, system)
        """
        with self._lock:
            try:
                log_entry = {
                    'timestamp': datetime.now().isoformat(),
                    'level': level,
                    'source': source,
                    'message': message
                }

                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(log_entry) + '\n')

            except Exception as e:
                print(f"Error writing log: {e}")

    def stream_logs(self, tail: int = 100) -> Generator[str, None, None]:
        """
        Stream logs as Server-Sent Events

        Args:
            tail: Number of recent log lines to send first

        Yields:
            SSE formatted log entries
        """
        # Send initial logs (last N lines)
        if self.log_file.exists():
            try:
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    recent_lines = lines[-tail:] if len(lines) > tail else lines

                    for line in recent_lines:
                        if line.strip():
                            yield f"data: {line}\n\n"
            except Exception as e:
                error_msg = json.dumps({
                    'timestamp': datetime.now().isoformat(),
                    'level': 'error',
                    'source': 'system',
                    'message': f'Error reading logs: {str(e)}'
                })
                yield f"data: {error_msg}\n\n"

        # Stream new logs in real-time
        last_position = self.log_file.stat().st_size if self.log_file.exists() else 0

        while True:
            try:
                if self.log_file.exists():
                    current_size = self.log_file.stat().st_size

                    if current_size > last_position:
                        with open(self.log_file, 'r', encoding='utf-8') as f:
                            f.seek(last_position)
                            new_content = f.read()

                            for line in new_content.strip().split('\n'):
                                if line.strip():
                                    yield f"data: {line}\n\n"

                            last_position = current_size

                # Send heartbeat every 15 seconds to keep connection alive
                heartbeat = json.dumps({
                    'timestamp': datetime.now().isoformat(),
                    'type': 'heartbeat'
                })
                yield f": {heartbeat}\n\n"

                time.sleep(1)  # Check for new logs every second

            except GeneratorExit:
                break
            except Exception as e:
                error_msg = json.dumps({
                    'timestamp': datetime.now().isoformat(),
                    'level': 'error',
                    'source': 'system',
                    'message': f'Stream error: {str(e)}'
                })
                yield f"data: {error_msg}\n\n"
                time.sleep(1)

    def clear_logs(self):
        """Clear log file"""
        with self._lock:
            try:
                if self.log_file.exists():
                    self.log_file.unlink()
                self.log_file.touch()
            except Exception as e:
                print(f"Error clearing logs: {e}")


# Global instance
log_streamer = LogStreamer()
