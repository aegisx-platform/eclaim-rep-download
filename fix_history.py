#!/usr/bin/env python3
"""
Fix download history file - remove 'GetFileAction.do?fn=' prefix from filenames
"""

import json
from pathlib import Path

history_file = Path('download_history.json')

if history_file.exists():
    with open(history_file, 'r', encoding='utf-8') as f:
        history = json.load(f)

    print(f"Fixing {len(history['downloads'])} records...")

    for record in history['downloads']:
        old_filename = record['filename']
        old_path = record['file_path']

        # Remove 'GetFileAction.do?fn=' prefix
        if old_filename.startswith('GetFileAction.do?fn='):
            new_filename = old_filename.replace('GetFileAction.do?fn=', '')
            new_path = old_path.replace('GetFileAction.do?fn=', '')

            record['filename'] = new_filename
            record['file_path'] = new_path

            print(f"  Fixed: {new_filename}")

    # Save updated history
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Fixed {len(history['downloads'])} records")
    print(f"✓ Saved to {history_file}")
else:
    print("✗ No history file found")
