# Master Data API Blueprint Extraction Summary

## Overview
Extracted all master data and health offices API routes from `app.py` into a new blueprint: `routes/master_data_api.py`

## Extracted Routes (17 total)

### Health Offices Routes (5 routes)
1. `GET  /api/health-offices` - Get health offices with filtering and pagination
2. `GET  /api/health-offices/stats` - Get health offices statistics
3. `POST /api/health-offices/import` - Import health offices from uploaded Excel file
4. `POST /api/health-offices/clear` - Clear all health offices data
5. `GET  /api/health-offices/lookup/<code>` - Lookup health office by code (hcode5 or hcode9)

### Master Data Count APIs (5 routes)
6. `GET /api/master-data/health-offices/count` - Get count of health offices
7. `GET /api/master-data/error-codes/count` - Get count of NHSO error codes
8. `GET /api/master-data/fund-types/count` - Get count of fund types
9. `GET /api/master-data/service-types/count` - Get count of service types
10. `GET /api/master-data/dim-date/count` - Get count of date dimension records

### Master Data List APIs (7 routes)
11. `GET /api/master-data/error-codes` - Get NHSO error codes with pagination
12. `GET /api/master-data/error-codes/<code>` - Get error code details by code
13. `GET /api/master-data/fund-types` - Get fund types with pagination
14. `GET /api/master-data/service-types` - Get service types with pagination
15. `GET /api/master-data/dim-date` - Get date dimension with pagination
16. `GET /api/master-data/dim-date/coverage` - Get date dimension coverage information
17. `POST /api/master-data/dim-date/generate` - Generate date dimension data

## Files Modified

### Created
- `routes/master_data_api.py` - New blueprint with all 17 master data routes

### Modified
- `app.py` - Added blueprint import and registration:
  - Import: `from routes.master_data_api import master_data_api_bp`
  - Registration: `app.register_blueprint(master_data_api_bp)`

## Dependencies Included

The blueprint includes all necessary imports:
- Flask (`Blueprint`, `jsonify`, `request`, `current_app`)
- `flask_login` (`login_required`)
- Database utilities (`get_db_connection` via app context)
- Configuration (`DB_TYPE` from `config.database`)
- Logging (`safe_format_exception` from `utils.logging_config`)
- Data processing (`pandas`, `openpyxl`, `io`, `re`, `time`, `datetime`)

## Helper Functions

Included in the blueprint:
- `get_db_connection()` - Get database connection from pool via app context
- `parse_formula_value()` - Parse Excel formula values (used in health offices import)
- `parse_date()` - Parse Thai Buddhist Era dates (used in health offices import)
- `clean_code()` - Clean and validate hospital codes (used in health offices import)

## Authentication

Routes with authentication:
- All `/api/master-data/*` routes require `@login_required`
- `/api/health-offices/*` routes are public (no authentication required)

## Database Tables Used

- `health_offices` - Health office master data
- `health_offices_import_log` - Health office import history
- `nhso_error_codes` - NHSO error code reference
- `fund_types` - Fund/scheme type reference
- `service_types` - Service type reference
- `dim_date` - Date dimension table

## Next Steps

1. The original routes remain in `app.py` as duplicates (backward compatibility)
2. Test the new blueprint endpoints to ensure they work correctly
3. Once verified, remove the duplicate routes from `app.py`
4. Update any frontend code that calls these endpoints (if needed)

## Verification

Total routes extracted: **17**
- Health Offices: 5 routes
- Master Data Counts: 5 routes
- Master Data Lists: 7 routes

All routes successfully extracted and blueprint registered in app.py.
