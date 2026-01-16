# Route Redesign Plan

## Design Principles

1. **All API endpoints under `/api/`** - No legacy routes without prefix
2. **RESTful conventions** - Use nouns for resources, HTTP methods for actions
3. **Consistent naming** - Use `analytics` (not `analysis`), `downloads` (not `trigger`)
4. **Group by resource** - REP, STM, SMT as sub-resources
5. **Predictable patterns** - Same operations follow same structure across types

## Current Issues Summary

| Issue | Current State | Impact |
|-------|---------------|--------|
| Legacy routes | `/download/trigger`, `/import/all` | No `/api/` prefix |
| Duplicate namespaces | `/api/analysis/` AND `/api/analytics/` | Confusing, duplicate code |
| Scattered imports | 4 different prefixes | No unified interface |
| Inconsistent clear | `clear-all`, `clear-database`, `clear` | Hard to discover |
| Parameter types | `<filename>` vs `<path:filename>` | Unexpected behavior |

---

## New Route Structure

### Page Routes (HTML Templates)

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Redirect to dashboard |
| `/dashboard` | GET | Main dashboard |
| `/setup` | GET | Initial setup wizard |
| `/files` | GET | File management |
| `/settings` | GET | Settings page |
| `/download` | GET | Download configuration |
| `/analytics` | GET | Analytics dashboard |
| `/reconciliation` | GET | Reconciliation page |
| `/data-management` | GET | Data management |
| `/predictive` | GET | Predictive analysis |
| `/benchmark` | GET | Benchmark page |
| `/logs` | GET | Log viewer |

---

### API Routes

#### Files & Downloads

```
GET  /api/files                           # List all files (with ?type=rep|stm|smt filter)
GET  /api/files/status                    # Get file status summary
POST /api/files/scan                      # Scan disk for new files
DELETE /api/files/<type>/<filename>       # Delete specific file

POST /api/downloads/single                # Download single file
POST /api/downloads/bulk                  # Bulk download (date range)
POST /api/downloads/parallel              # Parallel download
GET  /api/downloads/progress              # Get download progress
POST /api/downloads/cancel                # Cancel current download
```

#### Import Operations

```
POST /api/imports/rep                     # Import all REP files
POST /api/imports/rep/<filename>          # Import single REP file
POST /api/imports/stm                     # Import all STM files
POST /api/imports/stm/<filename>          # Import single STM file
POST /api/imports/smt                     # Import all SMT files
POST /api/imports/smt/<filename>          # Import single SMT file
GET  /api/imports/progress                # Get import progress
```

#### Data Sources - REP (Reimbursement)

```
GET  /api/rep/files                       # List REP files
GET  /api/rep/records                     # Get REP records (paginated)
GET  /api/rep/records/<tran_id>           # Get single REP record
POST /api/rep/download                    # Trigger REP download
POST /api/rep/clear                       # Clear REP data
```

#### Data Sources - STM (Statement)

```
GET  /api/stm/files                       # List STM files
GET  /api/stm/records                     # Get STM records (paginated)
GET  /api/stm/reconciliation              # Reconciliation summary
POST /api/stm/download                    # Trigger STM download
POST /api/stm/clear                       # Clear STM data
GET  /api/stm/schedule                    # Get STM schedule
POST /api/stm/schedule                    # Set STM schedule
```

#### Data Sources - SMT (Smart Money Transfer)

```
GET  /api/smt/files                       # List SMT files
GET  /api/smt/status                      # SMT budget status
GET  /api/smt/budget                      # Get budget data
POST /api/smt/download                    # Fetch SMT data (API)
POST /api/smt/clear                       # Clear SMT data
```

#### Analytics (Unified - remove /analysis/)

```
GET  /api/analytics/overview              # Dashboard overview stats
GET  /api/analytics/claims                # Claims analysis
GET  /api/analytics/claims/by-month       # Monthly breakdown
GET  /api/analytics/claims/by-scheme      # By scheme (UCS, OFC, etc)
GET  /api/analytics/denial                # Denial analysis
GET  /api/analytics/denial/reasons        # Denial reasons breakdown
GET  /api/analytics/errors                # Error analysis
GET  /api/analytics/errors/codes          # Error codes breakdown
GET  /api/analytics/reconciliation        # Reconciliation stats
GET  /api/analytics/trends                # Trend analysis
GET  /api/analytics/forecast              # Revenue forecasting
GET  /api/analytics/benchmark             # Benchmark comparison
```

#### History & Logs

```
GET  /api/history/downloads               # Download history
POST /api/history/downloads/clear         # Clear download history
GET  /api/history/downloads/failed        # Get failed downloads
POST /api/history/downloads/retry/<id>    # Retry failed download
GET  /api/history/jobs                    # Job execution history
GET  /api/history/imports                 # Import history
```

#### System & Settings

```
GET  /api/system/health                   # Health check
GET  /api/system/stats                    # System statistics
GET  /api/system/logs                     # Recent logs

GET  /api/settings                        # Get all settings
PUT  /api/settings                        # Update settings
PUT  /api/settings/credentials            # Update credentials

GET  /api/schedule                        # Get schedule config
POST /api/schedule                        # Update schedule
POST /api/schedule/test                   # Test schedule
```

#### Reference Data

```
GET  /api/health-offices                  # List health offices
GET  /api/health-offices/<code>           # Get single health office
POST /api/health-offices/import           # Import health offices

GET  /api/error-codes                     # List NHSO error codes
GET  /api/error-codes/<code>              # Get single error code
```

#### Alerts & Notifications

```
GET  /api/alerts                          # List active alerts
GET  /api/alerts/<id>                     # Get single alert
POST /api/alerts/<id>/dismiss             # Dismiss alert
POST /api/alerts/<id>/acknowledge         # Acknowledge alert
```

#### Predictive Analysis

```
GET  /api/predictive/forecast             # Revenue forecast
GET  /api/predictive/anomalies            # Anomaly detection
GET  /api/predictive/recommendations      # Recommendations
```

---

## Migration Plan

### Phase 1: Add New Routes (Backward Compatible)

1. Create new route handlers with new paths
2. Keep old routes working (redirect or alias)
3. Update frontend to use new routes
4. Add deprecation warnings to old routes

### Phase 2: Update Frontend

1. Update all fetch/ajax calls to new endpoints
2. Update any hardcoded URLs
3. Test thoroughly

### Phase 3: Remove Old Routes

1. Remove legacy routes
2. Clean up duplicate code
3. Update documentation

---

## Route Mapping (Old → New)

### Downloads
| Old | New |
|-----|-----|
| `POST /download/trigger` | `POST /api/downloads/single` |
| `POST /download/trigger/bulk` | `POST /api/downloads/bulk` |
| `POST /api/download/parallel` | `POST /api/downloads/parallel` |
| `GET /download/status` | `GET /api/downloads/progress` |
| `GET /download/bulk/progress` | `GET /api/downloads/progress` |
| `POST /download/bulk/cancel` | `POST /api/downloads/cancel` |

### Imports
| Old | New |
|-----|-----|
| `POST /import/all` | `POST /api/imports/rep` |
| `POST /import/file/<filename>` | `POST /api/imports/rep/<filename>` |
| `POST /api/stm/import-all` | `POST /api/imports/stm` |
| `POST /api/stm/import/<filename>` | `POST /api/imports/stm/<filename>` |
| `POST /api/smt/import-all` | `POST /api/imports/smt` |
| `GET /import/progress` | `GET /api/imports/progress` |

### Analytics (Merge /analysis/ into /analytics/)
| Old | New |
|-----|-----|
| `GET /api/analysis/summary` | `GET /api/analytics/overview` |
| `GET /api/analysis/claims` | `GET /api/analytics/claims` |
| `GET /api/analysis/reconciliation` | `GET /api/analytics/reconciliation` |
| `GET /api/analysis/errors` | `GET /api/analytics/errors` |

### Files
| Old | New |
|-----|-----|
| `GET /api/files/update-status` | `GET /api/files/status` |
| `POST /api/files/scan` | `POST /api/files/scan` (unchanged) |
| `DELETE /files/<filename>/delete` | `DELETE /api/files/rep/<filename>` |
| `DELETE /api/stm/delete/<filename>` | `DELETE /api/files/stm/<filename>` |
| `DELETE /api/smt/delete/<filename>` | `DELETE /api/files/smt/<filename>` |

### Clear Operations
| Old | New |
|-----|-----|
| `POST /api/clear-all` | `POST /api/data/clear-all` |
| `POST /api/rep/clear-database` | `POST /api/rep/clear` |
| `POST /api/stm/clear-database` | `POST /api/stm/clear` |
| `POST /api/smt/clear` | `POST /api/smt/clear` (unchanged) |

### History
| Old | New |
|-----|-----|
| `POST /api/download-history/clear` | `POST /api/history/downloads/clear` |
| `GET /api/download-history/failed` | `GET /api/history/downloads/failed` |
| `POST /api/download-history/reset-failed` | `POST /api/history/downloads/retry-all` |

---

## Blueprint Organization (Future)

```python
# blueprints/
#   __init__.py
#   files.py        # /api/files/*
#   downloads.py    # /api/downloads/*
#   imports.py      # /api/imports/*
#   rep.py          # /api/rep/*
#   stm.py          # /api/stm/*
#   smt.py          # /api/smt/*
#   analytics.py    # /api/analytics/*
#   history.py      # /api/history/*
#   system.py       # /api/system/*, /api/settings/*
#   alerts.py       # /api/alerts/*
#   predictive.py   # /api/predictive/*
```

---

## Checklist

- [ ] Create new route handlers
- [ ] Add backward-compatible aliases
- [ ] Update setup.html frontend
- [ ] Update dashboard.html frontend
- [ ] Update files.html frontend
- [ ] Update all other templates
- [ ] Update static/js/app.js
- [ ] Add deprecation warnings
- [ ] Update CLAUDE.md documentation
- [ ] Test all endpoints
- [ ] Remove old routes
