# Alerts API Routes List

## All Routes in alerts_api.py

| # | Method | Endpoint | Function | Description |
|---|--------|----------|----------|-------------|
| 1 | GET | /api/alerts | get_alerts() | Get system alerts with filtering (type, severity, dismissed) |
| 2 | GET | /api/alerts/unread-count | get_alerts_unread_count() | Get count of unread alerts |
| 3 | POST | /api/alerts/<alert_id>/read | mark_alert_read() | Mark a specific alert as read |
| 4 | POST | /api/alerts/read-all | mark_all_alerts_read() | Mark all alerts as read |
| 5 | POST | /api/alerts/<alert_id>/dismiss | dismiss_alert() | Dismiss a specific alert |
| 6 | POST | /api/alerts/dismiss-all | dismiss_all_alerts() | Dismiss all alerts |
| 7 | POST | /api/alerts/check-health | check_health_and_alert() | Check system health and create alerts |

## Query Parameters

### GET /api/alerts
- `include_dismissed` (boolean) - Include dismissed alerts (default: false)
- `type` (string) - Filter by alert type
- `severity` (string) - Filter by severity level
- `limit` (int) - Max results (default: 50, max: 200)

## Health Check Details

### POST /api/alerts/check-health

Monitors and creates alerts for:

1. **Disk Space**
   - Threshold: >80% used
   - Alert type: `disk_warning`
   - Data: used_percent, free_gb

2. **Memory Usage**
   - Threshold: >80% used
   - Alert type: `memory_warning`
   - Data: memory_percent, available_gb

3. **Stale Processes**
   - Checks PID files:
     - `/tmp/eclaim_downloader.pid`
     - `/tmp/eclaim_import.pid`
     - `/tmp/eclaim_parallel_download.pid`
   - Alert type: `stale_process`
   - Triggers if PID file exists but process doesn't

## Response Format

### Success Response
```json
{
  "success": true,
  "alerts": [...],  // or other data
  "total": 10       // or other fields
}
```

### Error Response
```json
{
  "success": false,
  "error": "Error message"
}
```
HTTP Status: 500

## Dependencies

### Python Modules
- `psutil` - System monitoring
- `shutil` - Disk usage
- `pathlib` - File path handling

### Internal Utils
- `alert_manager` - Alert CRUD operations
- `DOWNLOADS_DIR` - Base directory for monitoring

## Integration

The blueprint is registered in `app.py`:
```python
from routes.alerts_api import alerts_api_bp
app.register_blueprint(alerts_api_bp)
```

Logs are written to: `logs/alerts_api.log`
