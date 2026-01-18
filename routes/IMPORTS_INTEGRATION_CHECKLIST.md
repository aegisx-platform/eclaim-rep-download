# Imports API Blueprint Integration Checklist

## Completed Tasks ✓

- [x] Created `routes/imports_api.py` with all import routes
- [x] Extracted 10 route functions (REP: 4, STM: 3, SMT: 3)
- [x] Preserved 10 modern routes + 9 legacy aliases = 19 total route decorators
- [x] Verified all dependencies are correctly imported
- [x] Changed `@app.route` to `@imports_api_bp.route`
- [x] Changed direct manager access to `current_app.config` access
- [x] Changed `app.logger` to `current_app.logger`
- [x] Preserved all error handling and status codes
- [x] Preserved all validation logic (STM prefix check, secure_filename)
- [x] Created documentation (IMPORTS_EXTRACTION_SUMMARY.md)
- [x] Created removal guide (IMPORTS_ROUTES_TO_REMOVE.md)

## Pending Tasks (Next Steps)

### 1. Update app.py
- [ ] Add import statement (after line 45):
  ```python
  from routes.imports_api import imports_api_bp
  ```

- [ ] Register blueprint (after existing blueprint registrations):
  ```python
  app.register_blueprint(imports_api_bp)
  ```

- [ ] Set config dependencies (after manager initialization):
  ```python
  app.config['FILE_MANAGER'] = file_manager
  app.config['UNIFIED_IMPORT_RUNNER'] = unified_import_runner
  ```

- [ ] Remove old route functions:
  - Lines 1291-1350 (REP imports)
  - Lines 1943-1999 (STM imports)
  - Lines 4379-4436 (SMT imports)
  - Total: ~175 lines to delete

### 2. Test All Endpoints

#### REP Import Tests
- [ ] `POST /api/imports/rep/<filename>` - Import single REP file
- [ ] `POST /import/file/<filename>` - Legacy alias works
- [ ] `POST /api/imports/rep` - Import all REP files
- [ ] `POST /import/all` - Legacy alias works
- [ ] `GET /api/imports/progress` - Get import progress
- [ ] `GET /import/progress` - Legacy alias works
- [ ] `POST /api/imports/cancel` - Cancel import
- [ ] Test error cases (file not found, already running)

#### STM Import Tests
- [ ] `POST /api/imports/stm/<filename>` - Import single STM file
- [ ] `POST /api/stm/import/<filename>` - Legacy alias works
- [ ] `POST /api/imports/stm` - Import all STM files
- [ ] `POST /api/stm/import-all` - Legacy alias works
- [ ] `GET /api/imports/stm/progress` - Get STM import progress
- [ ] `GET /api/stm/import/progress` - Legacy alias works
- [ ] Test STM validation (must start with 'STM_')
- [ ] Test error cases

#### SMT Import Tests
- [ ] `POST /api/imports/smt/<path:filename>` - Import single SMT file
- [ ] `POST /api/smt/import/<path:filename>` - Legacy alias works
- [ ] `POST /api/imports/smt` - Import all SMT files
- [ ] `POST /api/smt/import-all` - Legacy alias works
- [ ] `GET /api/imports/smt/progress` - Get SMT import progress
- [ ] `GET /api/smt/import/progress` - Legacy alias works
- [ ] Test filename sanitization (secure_filename)
- [ ] Test error cases

### 3. Verify Integration

- [ ] Flask app starts without errors
- [ ] Blueprint is registered (check startup logs)
- [ ] Config dependencies are available
- [ ] No duplicate route warnings
- [ ] All routes respond correctly
- [ ] Error handling works as expected
- [ ] Logging works (check for STM/SMT error logs)
- [ ] Progress tracking works across all types
- [ ] Cancel functionality works

### 4. Code Quality Checks

- [ ] No unused imports in imports_api.py
- [ ] No syntax errors
- [ ] Consistent naming conventions
- [ ] Proper docstrings maintained
- [ ] Error messages are user-friendly
- [ ] HTTP status codes are correct (200, 400, 404, 409, 500)

### 5. Backward Compatibility

- [ ] All legacy routes still work
- [ ] API responses unchanged
- [ ] Error response format unchanged
- [ ] Progress response format unchanged
- [ ] Frontend/client integration unaffected

## Verification Commands

```bash
# Verify blueprint file exists
ls -lh routes/imports_api.py

# Count routes in blueprint
grep -c "^@imports_api_bp.route" routes/imports_api.py
# Expected: 19

# Verify import in app.py
grep "from routes.imports_api import" app.py
# Expected: Should see import statement

# Verify registration in app.py
grep "register_blueprint(imports_api_bp)" app.py
# Expected: Should see registration

# Verify config in app.py
grep "app.config\['UNIFIED_IMPORT_RUNNER'\]" app.py
# Expected: Should see config assignment

# Verify old routes removed from app.py
grep -n "^def import_file\|^def import_all_files\|^def import_stm_file_route" app.py
# Expected: No results

# Verify health_offices_import NOT removed
grep -n "def api_health_offices_import" app.py
# Expected: Should still exist

# Test endpoint availability
curl -X POST http://localhost:5001/api/imports/rep
curl -X POST http://localhost:5001/import/all  # Legacy
curl http://localhost:5001/api/imports/progress
```

## Known Issues / Edge Cases

None identified yet. Update this section after testing.

## Rollback Plan

If integration fails:
1. Restore app.py from git: `git checkout app.py`
2. Remove imports_api.py: `rm routes/imports_api.py`
3. Restart application
4. Investigate errors and re-attempt

## Files Modified

- ✓ **Created**: `routes/imports_api.py` (new file, 233 lines)
- ✓ **Created**: `routes/IMPORTS_EXTRACTION_SUMMARY.md` (documentation)
- ✓ **Created**: `routes/IMPORTS_ROUTES_TO_REMOVE.md` (removal guide)
- ✓ **Created**: `routes/IMPORTS_INTEGRATION_CHECKLIST.md` (this file)
- ⏳ **To Modify**: `app.py` (add import, register blueprint, set config, remove old routes)

## Success Criteria

Integration is successful when:
1. Flask app starts without errors
2. All 19 routes (10 modern + 9 legacy) respond correctly
3. No duplicate route warnings
4. All tests pass
5. Backward compatibility maintained
6. ~175 lines removed from app.py
7. Code is more maintainable and modular

## Notes

- Blueprint name: `imports_api`
- Route prefix: None (routes maintain their original paths)
- Config keys: `FILE_MANAGER`, `UNIFIED_IMPORT_RUNNER`
- Legacy routes must continue working for backward compatibility
- Delete routes are NOT in this blueprint (they belong to files_api.py)
