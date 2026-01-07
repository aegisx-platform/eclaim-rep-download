"""File Manager - Safe file operations with security"""

import os
from pathlib import Path
import humanize
from .history_manager import HistoryManager


class FileManager:
    def __init__(self, download_dir='downloads'):
        self.download_dir = Path(download_dir).resolve()
        self.history_manager = HistoryManager()

        # Ensure download directory exists
        self.download_dir.mkdir(exist_ok=True)

    def get_file_path(self, filename):
        """Resolve safe file path within downloads directory"""
        # Sanitize filename - remove any path components
        filename = os.path.basename(filename)

        # Validate filename
        if '..' in filename or filename.startswith('/'):
            raise ValueError("Invalid filename: path traversal detected")

        # Build full path
        file_path = self.download_dir / filename

        # Verify path is within downloads directory
        try:
            file_path.resolve().relative_to(self.download_dir)
        except ValueError:
            raise ValueError("Invalid filename: path outside downloads directory")

        return file_path

    def file_exists(self, filename):
        """Check if file exists"""
        try:
            file_path = self.get_file_path(filename)
            return file_path.exists()
        except ValueError:
            return False

    def get_file_stats(self, filename):
        """Get file metadata"""
        file_path = self.get_file_path(filename)

        if not file_path.exists():
            return None

        stat = file_path.stat()

        return {
            'filename': filename,
            'size': stat.st_size,
            'size_formatted': humanize.naturalsize(stat.st_size),
            'modified': stat.st_mtime
        }

    def delete_file(self, filename):
        """Delete file from disk and remove from history"""
        # Get safe file path
        file_path = self.get_file_path(filename)

        # Check file exists
        if not file_path.exists():
            return False

        try:
            # Delete physical file
            file_path.unlink()

            # Remove from history
            self.history_manager.delete_download(filename)

            return True

        except Exception as e:
            print(f"Error deleting file {filename}: {e}")
            return False

    @staticmethod
    def format_size(size_bytes):
        """Format file size to human-readable string"""
        return humanize.naturalsize(size_bytes)

    def scan_orphaned_files(self):
        """Find files on disk not in history"""
        # Get all files in downloads directory
        disk_files = set()
        for file_path in self.download_dir.glob('*.xls'):
            disk_files.add(file_path.name)

        # Get all files in history
        history_files = set()
        downloads = self.history_manager.get_all_downloads()
        for download in downloads:
            history_files.add(download['filename'])

        # Find orphaned files (on disk but not in history)
        orphaned = disk_files - history_files

        return list(orphaned)
