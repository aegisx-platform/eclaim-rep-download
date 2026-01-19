# Imports API Routes Quick Reference

## Blueprint Information
- **File**: `routes/imports_api.py`
- **Blueprint Name**: `imports_api_bp`
- **Total Functions**: 10
- **Total Routes**: 19 (10 modern + 9 legacy aliases)

## Routes Overview

### REP (E-Claim Reimbursement) Import Routes

| Method | Modern Route | Legacy Alias | Function | Description |
|--------|--------------|--------------|----------|-------------|
| POST | `/api/imports/rep/<filename>` | `/import/file/<filename>` | `import_file()` | Import single REP file |
| POST | `/api/imports/rep` | `/import/all` | `import_all_files()` | Import all REP files |
| GET | `/api/imports/progress` | `/import/progress` | `import_progress()` | Get import progress (unified) |
| POST | `/api/imports/cancel` | - | `cancel_import()` | Cancel running import |

### STM (Statement) Import Routes

| Method | Modern Route | Legacy Alias | Function | Description |
|--------|--------------|--------------|----------|-------------|
| POST | `/api/imports/stm/<filename>` | `/api/stm/import/<filename>` | `import_stm_file_route()` | Import single STM file |
| POST | `/api/imports/stm` | `/api/stm/import-all` | `import_all_stm_files()` | Import all STM files |
| GET | `/api/imports/stm/progress` | `/api/stm/import/progress` | `stm_import_progress()` | Get STM import progress |

### SMT (Smart Money Transfer) Import Routes

| Method | Modern Route | Legacy Alias | Function | Description |
|--------|--------------|--------------|----------|-------------|
| POST | `/api/imports/smt/<path:filename>` | `/api/smt/import/<path:filename>` | `api_smt_import_file()` | Import single SMT file |
| POST | `/api/imports/smt` | `/api/smt/import-all` | `api_smt_import_all()` | Import all SMT files |
| GET | `/api/imports/smt/progress` | `/api/smt/import/progress` | `smt_import_progress()` | Get SMT import progress |

## Route Details

### REP Import Endpoints

#### 1. Import Single REP File
```
POST /api/imports/rep/<filename>
POST /import/file/<filename>  (legacy)
```
**Request**: None  
**Response**: `{success: bool, message: str, process_id?: str}`  
**Status Codes**: 200 (success), 404 (not found), 409 (already running), 500 (error)

#### 2. Import All REP Files
```
POST /api/imports/rep
POST /import/all  (legacy)
```
**Request**: None  
**Response**: `{success: bool, message: str, process_id?: str}`  
**Status Codes**: 200 (success), 409 (already running), 500 (error)

#### 3. Get Import Progress
```
GET /api/imports/progress
GET /import/progress  (legacy)
```
**Request**: None  
**Response**: `{success: bool, progress: {...}, running?: bool}`  
**Status Codes**: 200 (success), 500 (error)

#### 4. Cancel Import
```
POST /api/imports/cancel
```
**Request**: None  
**Response**: `{success: bool, message: str}`  
**Status Codes**: 200 (success), 500 (error)

### STM Import Endpoints

#### 5. Import Single STM File
```
POST /api/imports/stm/<filename>
POST /api/stm/import/<filename>  (legacy)
```
**Validation**: Filename must start with 'STM_'  
**Response**: `{success: bool, message: str, process_id?: str}`  
**Status Codes**: 200 (success), 400 (invalid), 404 (not found), 409 (already running), 500 (error)

#### 6. Import All STM Files
```
POST /api/imports/stm
POST /api/stm/import-all  (legacy)
```
**Response**: `{success: bool, message: str, process_id?: str}`  
**Status Codes**: 200 (success), 409 (already running), 500 (error)

#### 7. Get STM Import Progress
```
GET /api/imports/stm/progress
GET /api/stm/import/progress  (legacy)
```
**Response**: `{success: bool, progress: {...}}`  
**Status Codes**: 200 (success), 500 (error)

### SMT Import Endpoints

#### 8. Import Single SMT File
```
POST /api/imports/smt/<path:filename>
POST /api/smt/import/<path:filename>  (legacy)
```
**Note**: Filename is sanitized using `secure_filename()`  
**Response**: `{success: bool, message: str, process_id?: str}`  
**Status Codes**: 200 (success), 404 (not found), 409 (already running), 500 (error)

#### 9. Import All SMT Files
```
POST /api/imports/smt
POST /api/smt/import-all  (legacy)
```
**Validation**: `downloads/smt/` directory must exist  
**Response**: `{success: bool, message: str, process_id?: str}`  
**Status Codes**: 200 (success), 400 (no directory), 409 (already running), 500 (error)

#### 10. Get SMT Import Progress
```
GET /api/imports/smt/progress
GET /api/smt/import/progress  (legacy)
```
**Response**: `{success: bool, progress: {...}}`  
**Status Codes**: 200 (success), 500 (error)

## Dependencies

### Config Requirements
Routes expect these keys in `current_app.config`:
- `FILE_MANAGER` - File path resolution and validation
- `UNIFIED_IMPORT_RUNNER` - Import process management

### Python Imports
```python
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required  # For future authentication
from werkzeug.utils import secure_filename
from pathlib import Path
```

## Integration Example

```python
# In app.py
from routes.imports_api import imports_api_bp

# Set config dependencies
app.config['FILE_MANAGER'] = file_manager
app.config['UNIFIED_IMPORT_RUNNER'] = unified_import_runner

# Register blueprint
app.register_blueprint(imports_api_bp)
```

## Testing Examples

```bash
# Import single REP file
curl -X POST http://localhost:5001/api/imports/rep/REP_10670_202512.xls

# Import all REP files (legacy route)
curl -X POST http://localhost:5001/import/all

# Check progress
curl http://localhost:5001/api/imports/progress

# Import STM file
curl -X POST http://localhost:5001/api/imports/stm/STM_10670_202512.xlsx

# Import all SMT files (legacy)
curl -X POST http://localhost:5001/api/smt/import-all

# Cancel import
curl -X POST http://localhost:5001/api/imports/cancel
```

## Notes

- All progress endpoints use the unified import runner, so they return the same progress data
- Legacy routes are maintained for backward compatibility
- STM files must start with 'STM_' prefix
- SMT filenames are sanitized for security
- All imports run as background processes
- Only one import can run at a time (409 Conflict if already running)
