# Complete List of Extracted Analytics Routes

This document lists all 53 route decorators extracted to `routes/analytics_api.py`.

## Analytics Routes (32 routes)

| Route | Function | Description |
|-------|----------|-------------|
| `/api/analytics/summary` | `api_analysis_summary()` | Summary statistics with filters |
| `/api/analytics/reconciliation` | `api_analysis_reconciliation()` | Reconciliation data |
| `/api/analytics/export` | `api_analysis_export()` | Export analytics data |
| `/api/analytics/search` | `api_analysis_search()` | Search claims |
| `/api/analytics/files` | `api_analysis_files()` | Files analysis |
| `/api/analytics/file-items` | `api_analysis_file_items()` | File items detail |
| `/api/analytics/claims-detail` | `api_analysis_claims()` | Detailed claims |
| `/api/analytics/financial-breakdown` | `api_analysis_financial_breakdown()` | Financial breakdown |
| `/api/analytics/errors-detail` | `api_analysis_errors()` | Error analysis |
| `/api/analytics/scheme-summary` | `api_analysis_scheme_summary()` | Scheme summary |
| `/api/analytics/facilities` | `api_analysis_facilities()` | Facilities analysis |
| `/api/analytics/his-reconciliation` | `api_analysis_his_reconciliation()` | HIS reconciliation |
| `/api/analytics/fiscal-years` | `api_analytics_fiscal_years()` | Available fiscal years |
| `/api/analytics/filter-options` | `api_analytics_filter_options()` | Filter options |
| `/api/analytics/overview` | `api_analytics_overview()` | Overview dashboard |
| `/api/analytics/monthly-trend` | `api_analytics_monthly_trend()` | Monthly trends |
| `/api/analytics/service-type` | `api_analytics_service_type()` | Service type analysis |
| `/api/analytics/fund` | `api_analytics_fund()` | Fund analysis |
| `/api/analytics/drg` | `api_analytics_drg()` | DRG analysis |
| `/api/analytics/drug` | `api_analytics_drug()` | Drug analysis |
| `/api/analytics/instrument` | `api_analytics_instrument()` | Instrument analysis |
| `/api/analytics/denial` | `api_analytics_denial()` | Denial analysis |
| `/api/analytics/comparison` | `api_analytics_comparison()` | Comparison analytics |
| `/api/analytics/claims` | `api_claims_detail()` | Claims data |
| `/api/analytics/claim/<tran_id>` | `api_claim_single()` | Single claim detail |
| `/api/analytics/denial-root-cause` | `api_denial_root_cause()` | Denial root cause |
| `/api/analytics/efficiency` | `api_analytics_efficiency()` | Efficiency metrics |
| `/api/analytics/alerts` | `api_alerts()` | System alerts |
| `/api/analytics/forecast` | `api_revenue_forecast()` | Revenue forecast |
| `/api/analytics/yoy-comparison` | `api_yoy_comparison()` | Year-over-year comparison |
| `/api/analytics/export/<report_type>` | `api_export_report()` | Export specific report |
| `/api/analytics/benchmark` | `api_benchmark()` | Benchmark data |

## Legacy Aliases (12 routes)

These routes provide backward compatibility for the old `/api/analysis/*` naming:

| Legacy Route | Modern Route | Function |
|--------------|--------------|----------|
| `/api/analysis/summary` | `/api/analytics/summary` | `api_analysis_summary()` |
| `/api/analysis/reconciliation` | `/api/analytics/reconciliation` | `api_analysis_reconciliation()` |
| `/api/analysis/export` | `/api/analytics/export` | `api_analysis_export()` |
| `/api/analysis/search` | `/api/analytics/search` | `api_analysis_search()` |
| `/api/analysis/files` | `/api/analytics/files` | `api_analysis_files()` |
| `/api/analysis/file-items` | `/api/analytics/file-items` | `api_analysis_file_items()` |
| `/api/analysis/claims` | `/api/analytics/claims-detail` | `api_analysis_claims()` |
| `/api/analysis/financial-breakdown` | `/api/analytics/financial-breakdown` | `api_analysis_financial_breakdown()` |
| `/api/analysis/errors` | `/api/analytics/errors-detail` | `api_analysis_errors()` |
| `/api/analysis/scheme-summary` | `/api/analytics/scheme-summary` | `api_analysis_scheme_summary()` |
| `/api/analysis/facilities` | `/api/analytics/facilities` | `api_analysis_facilities()` |
| `/api/analysis/his-reconciliation` | `/api/analytics/his-reconciliation` | `api_analysis_his_reconciliation()` |

## Predictive Analytics Routes (8 routes)

| Route | Function | Description |
|-------|----------|-------------|
| `/api/predictive/denial-risk` | `api_denial_risk()` | Denial risk prediction |
| `/api/predictive/anomalies` | `api_anomalies()` | Anomaly detection |
| `/api/predictive/opportunities` | `api_opportunities()` | Revenue opportunities |
| `/api/predictive/insights` | `api_insights()` | AI insights |
| `/api/predictive/ml-info` | `api_ml_info()` | ML model info |
| `/api/predictive/ml-predict` | `api_ml_predict()` | ML prediction (POST) |
| `/api/predictive/ml-predict-batch` | `api_ml_predict_batch()` | Batch prediction (POST) |
| `/api/predictive/ml-high-risk` | `api_ml_high_risk()` | High risk claims |

## Dashboard Routes (1 route)

| Route | Function | Description |
|-------|----------|-------------|
| `/api/dashboard/reconciliation-status` | `api_dashboard_reconciliation_status()` | Reconciliation status |

## Summary

- **Total Routes:** 53 route decorators
- **Unique Functions:** 41 route handlers
- **Route Types:**
  - Modern analytics routes: 32
  - Legacy compatibility aliases: 12
  - Predictive analytics: 8
  - Dashboard: 1

All routes are now in `routes/analytics_api.py` as a Flask blueprint.
