# Analytics API Blueprint Extraction Summary

## File Created
**Location:** `routes/analytics_api.py`

## Statistics
- **Total Lines:** 5,685
- **Total Routes:** 53 route decorators
- **Total Functions:** 41 route handler functions
- **Helper Functions:** 12 (SQL helpers + utility functions)

## Routes Extracted

### Analytics Routes (/api/analytics/*)
1. `/api/analytics/summary` - Summary statistics with filters
2. `/api/analytics/reconciliation` - Reconciliation data
3. `/api/analytics/export` - Export analytics data
4. `/api/analytics/search` - Search claims
5. `/api/analytics/files` - Files analysis
6. `/api/analytics/file-items` - File items detail
7. `/api/analytics/claims-detail` - Detailed claims
8. `/api/analytics/financial-breakdown` - Financial breakdown
9. `/api/analytics/errors-detail` - Error analysis
10. `/api/analytics/scheme-summary` - Scheme summary
11. `/api/analytics/facilities` - Facilities analysis
12. `/api/analytics/his-reconciliation` - HIS reconciliation
13. `/api/analytics/fiscal-years` - Available fiscal years
14. `/api/analytics/filter-options` - Filter options
15. `/api/analytics/overview` - Overview dashboard
16. `/api/analytics/monthly-trend` - Monthly trends
17. `/api/analytics/service-type` - Service type analysis
18. `/api/analytics/fund` - Fund analysis
19. `/api/analytics/drg` - DRG analysis
20. `/api/analytics/drug` - Drug analysis
21. `/api/analytics/instrument` - Instrument analysis
22. `/api/analytics/denial` - Denial analysis
23. `/api/analytics/comparison` - Comparison analytics
24. `/api/analytics/claims` - Claims data
25. `/api/analytics/claim/<tran_id>` - Single claim detail
26. `/api/analytics/denial-root-cause` - Denial root cause
27. `/api/analytics/efficiency` - Efficiency metrics
28. `/api/analytics/alerts` - System alerts
29. `/api/analytics/forecast` - Revenue forecast
30. `/api/analytics/yoy-comparison` - Year-over-year comparison
31. `/api/analytics/export/<report_type>` - Export specific report
32. `/api/analytics/benchmark` - Benchmark data

### Legacy Aliases (/api/analysis/*)
All `/api/analytics/*` routes have `/api/analysis/*` legacy aliases (12 routes total)

### Predictive Routes (/api/predictive/*)
1. `/api/predictive/denial-risk` - Denial risk prediction
2. `/api/predictive/anomalies` - Anomaly detection
3. `/api/predictive/opportunities` - Revenue opportunities
4. `/api/predictive/insights` - AI insights
5. `/api/predictive/ml-info` - ML model info
6. `/api/predictive/ml-predict` - ML prediction (POST)
7. `/api/predictive/ml-predict-batch` - Batch prediction (POST)
8. `/api/predictive/ml-high-risk` - High risk claims

### Dashboard Routes
1. `/api/dashboard/reconciliation-status` - Reconciliation status

## Helper Functions Included

### SQL Compatibility Helpers (PostgreSQL/MySQL)
1. `sql_date_trunc_month(column)` - Truncate date to month
2. `sql_count_distinct_months(column)` - Count distinct months
3. `sql_current_month_start()` - Current month start
4. `sql_interval_months(months)` - Month interval
5. `sql_interval_days(days)` - Day interval
6. `sql_format_year_month(column)` - Format as YYYY-MM
7. `sql_format_month(column)` - Alias for year_month
8. `sql_cast_numeric(expr)` - Cast to numeric
9. `sql_coalesce_numeric(column, default)` - Coalesce with numeric
10. `sql_extract_year(column)` - Extract year
11. `sql_extract_month(column)` - Extract month
12. `sql_regex_match(column, pattern)` - Regex matching

### Analytics Utility Functions
1. `get_db_connection()` - Get pooled DB connection
2. `_validate_date_param(date_str)` - Validate date format
3. `get_analytics_date_filter()` - Build date filter from request
4. `get_available_fiscal_years(cursor)` - Get fiscal years from data

## Dependencies

### Imports
```python
import os, csv, io, traceback
from calendar import monthrange
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from zoneinfo import ZoneInfo
from flask import Blueprint, request, jsonify, Response, g, current_app
from flask_login import login_required
```

### Internal Modules
```python
from config.database import get_db_config, DB_TYPE
from config.db_pool import get_connection as get_pooled_connection
from utils.settings_manager import SettingsManager
from utils.fiscal_year import (
    get_fiscal_year_sql_filter_gregorian,
    get_fiscal_year_range_gregorian,
    get_fiscal_year_range_be
)
from utils.logging_config import safe_format_exception
```

### Runtime Imports (within routes)
- `from utils.ml.predictor import get_model_info` (in ML routes)
- `from utils.ml.predictor import get_predictor` (in ML routes)

## Changes Made

1. **Blueprint Creation:** Created `analytics_api_bp = Blueprint('analytics_api', __name__)`
2. **Route Decorator Replacement:** Changed all `@app.route(...)` to `@analytics_api_bp.route(...)`
3. **Logger References:** Changed `app.logger` to `current_app.logger` (45 occurrences)
4. **Helper Functions:** Copied SQL helper functions and analytics utilities
5. **Settings Manager:** Initialized `settings_manager = SettingsManager()` at module level

## Next Steps

**To integrate this blueprint into app.py:**

1. Import the blueprint:
   ```python
   from routes.analytics_api import analytics_api_bp
   ```

2. Register the blueprint:
   ```python
   app.register_blueprint(analytics_api_bp)
   ```

3. Remove the extracted routes from app.py (lines 1651-11497)

4. Keep SQL helper functions in app.py if other routes use them, or move to shared module

## Testing Checklist

- [ ] Verify blueprint imports successfully
- [ ] Verify blueprint registers without errors
- [ ] Test sample analytics route (e.g., `/api/analytics/summary`)
- [ ] Test legacy alias route (e.g., `/api/analysis/summary`)
- [ ] Test predictive route (e.g., `/api/predictive/denial-risk`)
- [ ] Test dashboard route (`/api/dashboard/reconciliation-status`)
- [ ] Verify database connections work
- [ ] Verify fiscal year functions work
- [ ] Check ML predictor imports (lazy loading)

## Notes

- All 41 routes maintain backward compatibility with legacy `/api/analysis/*` endpoints
- Database connection uses connection pooling via `get_db_connection()`
- Fiscal year calculations imported from `utils.fiscal_year` module
- ML predictor functions are imported dynamically within routes (lazy loading)
- Settings manager instance created at module level for efficiency
