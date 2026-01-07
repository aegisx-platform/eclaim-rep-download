# E-Claim Import System - Quick Start Guide

## 📋 Prerequisites

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Dependencies installed:
- `pandas` - Excel file processing
- `xlrd` - Read .xls files
- `psycopg2-binary` - PostgreSQL connector
- `pymysql` - MySQL connector
- `sqlalchemy` - Database abstraction

### 2. Create Database

**Option A: PostgreSQL (Recommended)**

```bash
# Create database
createdb eclaim_db

# Run schema
psql eclaim_db < database/schema.sql
```

**Option B: MySQL**

```bash
# Create database
mysql -u root -p -e "CREATE DATABASE eclaim_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# Run schema (requires conversion to MySQL syntax)
mysql -u root -p eclaim_db < database/schema.sql
```

### 3. Configure Database Connection

Create `.env` file or set environment variables:

```bash
# PostgreSQL (default)
export DB_TYPE=postgresql
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=eclaim_db
export DB_USER=postgres
export DB_PASSWORD=your_password

# Or MySQL
export DB_TYPE=mysql
export DB_HOST=localhost
export DB_PORT=3306
export DB_NAME=eclaim_db
export DB_USER=root
export DB_PASSWORD=your_password
```

---

## 🚀 Usage

### Analyze File (No Import)

Inspect XLS file structure without importing:

```bash
python eclaim_import.py --analyze downloads/eclaim_10670_OP_25680130_194509335.xls
```

Output:
```
File Type:     OP
Hospital Code: 10670
File Date:     2025-01-30
Total Rows:    284
Total Columns: 120
```

### Import Single File

```bash
python eclaim_import.py downloads/eclaim_10670_OP_25680130_194509335.xls
```

### Import All Files in Directory

```bash
# Import all .xls files
python eclaim_import.py --directory downloads/

# Import only IP files
python eclaim_import.py --directory downloads/ --pattern "*_IP_*.xls"

# Import only OP files
python eclaim_import.py --directory downloads/ --pattern "*_OP_*.xls"
```

### Import All Downloaded Files (Default)

If no arguments provided, imports all files in `downloads/` directory:

```bash
python eclaim_import.py
```

---

## 📊 Import Process

The import system follows this workflow:

```
1. Parse filename → Extract metadata (hospital, type, date)
2. Read XLS → Detect header row automatically
3. Create import record → Status: "processing"
4. Validate data → Check required fields
5. Import to database → UPSERT (handles duplicates)
6. Update status → "completed" or "failed"
```

### File Types Handled

| Type | Description | Table |
|------|-------------|-------|
| OP | Outpatient | eclaim_claims |
| IP | Inpatient | eclaim_claims |
| ORF | OP Refer | eclaim_op_refer |
| IP_APPEAL | IP Appeal (Hospital) | eclaim_claims |
| IP_APPEAL_NHSO | IP Appeal (NHSO) | eclaim_claims |

### Duplicate Handling

Uses **UPSERT** strategy:
- Primary key: `(tran_id, file_id)`
- On conflict: Updates `net_reimbursement`, `error_code`, `updated_at`
- Preserves reconciliation data from previous imports

---

## 📁 File Structure

```
eclaim-req-download/
├── eclaim_import.py           # Main CLI script
├── config/
│   └── database.py            # Database configuration
├── utils/
│   └── eclaim/
│       ├── parser.py          # XLS file parser
│       └── importer.py        # Database importer
├── database/
│   ├── schema.sql             # PostgreSQL schema
│   ├── ECLAIM_ANALYSIS_REPORT.md
│   └── IMPORT_GUIDE.md        # This file
└── downloads/                 # XLS files location
```

---

## 🔍 Verification

### Check Import Status

```sql
-- View all imported files
SELECT filename, file_type, status, total_records, imported_records
FROM eclaim_imported_files
ORDER BY created_at DESC;

-- Count records by file type
SELECT file_type, COUNT(*) as count
FROM eclaim_claims
GROUP BY file_type;

-- View recent claims
SELECT tran_id, hn, patient_name, net_reimbursement
FROM eclaim_claims
ORDER BY created_at DESC
LIMIT 10;
```

### Import Summary

```sql
-- Total imported vs failed
SELECT
    COUNT(*) as total_files,
    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
    SUM(total_records) as total_records,
    SUM(imported_records) as imported_records
FROM eclaim_imported_files;
```

---

## ⚠️ Troubleshooting

### Database Connection Failed

```
Error: Database connection failed: FATAL: password authentication failed
```

**Solution:** Check `.env` file or environment variables for correct credentials.

### Header Row Not Detected

```
Warning: Could not detect header row, defaulting to row 5
```

**Solution:** This is usually fine. E-Claim files have headers at row 5 or 7. The parser handles both.

### Import Failed: Duplicate Key

```
Error: duplicate key value violates unique constraint "eclaim_claims_tran_id_file_id_key"
```

**Solution:** This shouldn't happen due to UPSERT. If it does, check if file was already imported.

### Missing Columns

```
Error: KeyError: 'TRAN_ID'
```

**Solution:** File format may be different. Use `--analyze` to inspect column names first.

---

## 🔄 Re-importing Files

To re-import a file:

1. **Delete existing import record:**
   ```sql
   DELETE FROM eclaim_imported_files WHERE filename = 'eclaim_10670_OP_25680130_194509335.xls';
   -- CASCADE will delete associated claim records
   ```

2. **Re-run import:**
   ```bash
   python eclaim_import.py downloads/eclaim_10670_OP_25680130_194509335.xls
   ```

---

## 📈 Next Steps

After importing data, proceed with:

1. **HIS Reconciliation** - Match claims with HIS database
2. **Amount Validation** - Compare reimbursement vs billing
3. **Error Analysis** - Investigate denied claims
4. **Dashboard Creation** - Build reports and visualizations

See `ECLAIM_ANALYSIS_REPORT.md` for detailed reconciliation strategies.

---

## 🆘 Support

For issues or questions:
- Check logs in `logs/` directory
- Review `database/ECLAIM_ANALYSIS_REPORT.md` for technical details
- Inspect failed imports in `eclaim_imported_files` table

---

*Last updated: 2026-01-07*
