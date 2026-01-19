# Alerts API Blueprint Extraction Summary

## Overview
Successfully extracted all alerts/notifications API routes from `app.py` into a dedicated blueprint `routes/alerts_api.py`.

## Extracted Routes (7 total)

### Alert Management
1. **GET /api/alerts** - Get system alerts with filtering
2. **GET /api/alerts/unread-count** - Get count of unread alerts
3. **POST /api/alerts/<alert_id>/read** - Mark an alert as read
4. **POST /api/alerts/read-all** - Mark all alerts as read
5. **POST /api/alerts/<alert_id>/dismiss** - Dismiss an alert
6. **POST /api/alerts/dismiss-all** - Dismiss all alerts
7. **POST /api/alerts/check-health** - Check system health and create alerts

## File Details

### routes/alerts_api.py
- **Lines**: 167
- **Blueprint name**: `alerts_api_bp`
- **Logger**: `setup_logger('alerts_api', logging.INFO, 'logs/alerts_api.log')`

### Dependencies Used
- `flask.Blueprint`
- `flask.jsonify, request`
- `utils.alert_manager.alert_manager`
- `utils.logging_config.setup_logger`
- `psutil` (for system monitoring)
- `shutil` (for disk usage)
- `pathlib.Path`
- `config.database.DOWNLOADS_DIR`

## Integration Status

### app.py Changes
1. ✅ Added import: `from routes.alerts_api import alerts_api_bp`
2. ✅ Added registration: `app.register_blueprint(alerts_api_bp)` with logger message
3. ⏳ Original routes preserved in app.py (awaiting manual removal)

## Route Functionality

### GET /api/alerts
- Query params: `include_dismissed`, `type`, `severity`, `limit`
- Returns list of system alerts with filtering
- Max limit: 200

### GET /api/alerts/unread-count
- Returns count of unread alerts
- No parameters

### POST /api/alerts/<alert_id>/read
- Marks specific alert as read
- Returns success status

### POST /api/alerts/read-all
- Marks all alerts as read
- Returns number of affected alerts

### POST /api/alerts/<alert_id>/dismiss
- Dismisses specific alert
- Returns success status

### POST /api/alerts/dismiss-all
- Dismisses all alerts
- Returns number of affected alerts

### POST /api/alerts/check-health
- Checks system health (disk, memory, stale processes)
- Creates alerts for issues found
- Disk warning: triggered at >80% usage
- Memory warning: triggered at >80% usage
- Stale process detection: checks PID files for downloader, import, parallel jobs
- Returns list of created alerts

## Testing Checklist

- [ ] Test GET /api/alerts with various filters
- [ ] Test unread count endpoint
- [ ] Test marking alerts as read (single and all)
- [ ] Test dismissing alerts (single and all)
- [ ] Test health check endpoint
- [ ] Verify alert_manager integration works
- [ ] Check logs are written to logs/alerts_api.log
- [ ] Verify blueprint registration message appears in app logs

## Next Steps

1. ✅ Blueprint created and registered
2. ⏳ Remove duplicate routes from app.py (manual task)
3. ⏳ Test all endpoints
4. ⏳ Update API documentation if needed
