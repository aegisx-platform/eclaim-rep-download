# Import Routes to Remove from app.py

## Line Ranges to Delete

### REP Import Routes
- Lines 1291-1350 (60 lines)
  - `import_file()` - Lines 1291-1311
  - `import_all_files()` - Lines 1314-1328
  - `import_progress()` - Lines 1331-1340
  - `cancel_import()` - Lines 1343-1350

### STM Import Routes
- Lines 1943-1999 (57 lines)
  - `import_stm_file_route()` - Lines 1943-1966
  - `import_all_stm_files()` - Lines 1969-1985
  - `stm_import_progress()` - Lines 1988-1998

### SMT Import Routes
- Lines 4379-4436 (58 lines)
  - `api_smt_import_file()` - Lines 4379-4400
  - `api_smt_import_all()` - Lines 4403-4423
  - `smt_import_progress()` - Lines 4426-4436

## Total Lines to Remove: ~175 lines

## Verification Commands

```bash
# Count routes before removal
grep -c "^def import.*(" app.py
# Expected: Will decrease by 10 functions

# Verify specific functions are removed
grep -n "^def import_file\|^def import_all_files\|^def import_stm_file_route\|^def api_smt_import" app.py
# Expected: No results after removal

# Verify health_offices_import is NOT removed
grep -n "def api_health_offices_import" app.py
# Expected: Still found (this should NOT be removed)
```

## Notes
- DO NOT remove `api_health_offices_import()` - it's master data, not REP/STM/SMT
- Keep any helper functions like `get_import_status_map()` if they exist
- Delete routes are in files_api.py, not imports_api.py (correctly excluded)
