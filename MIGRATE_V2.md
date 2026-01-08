# 🚀 Quick Start: Migrate to Schema V2

## สำหรับผู้ที่เริ่มใหม่ (Fresh Install)

### MySQL

```bash
# 1. Clone repository
git clone https://github.com/aegisx-platform/eclaim-req-download.git
cd eclaim-req-download

# 2. Setup environment
cp .env.example .env
nano .env  # แก้ไข ECLAIM_USERNAME, ECLAIM_PASSWORD, DB_TYPE=mysql

# 3. Start MySQL stack
docker-compose -f docker-compose-mysql.yml up -d

# 4. Access Web UI
# http://localhost:5001
```

### PostgreSQL

```bash
# 1-2. Same as MySQL

# 3. Start PostgreSQL stack
docker-compose up -d

# 4. Access Web UI
# http://localhost:5001
```

**เสร็จแล้ว!** Schema V2 จะถูก import อัตโนมัติตอน container start ครั้งแรก

---

## สำหรับผู้ที่มี Database เดิมอยู่แล้ว

### ⚠️ คำเตือน

**Option A จะลบข้อมูลเดิมทั้งหมด!** ต้อง backup ก่อน

### วิธีที่ 1: ใช้ Migration Script (แนะนำ)

```bash
# รันสคริปต์อัตโนมัติ
./database/migrate_to_v2.sh
```

Script จะทำให้อัตโนมัติ:
1. ✅ Backup database เดิม → `backup_before_v2_YYYYMMDD_HHMMSS.sql`
2. ✅ Drop database เดิม
3. ✅ Create database ใหม่
4. ✅ Import schema V2
5. ✅ Verify tables

### วิธีที่ 2: Manual Migration

#### MySQL:

```bash
# 1. Backup
mysqldump -u eclaim -p eclaim_db > backup_before_v2.sql

# 2. Drop existing database
mysql -u eclaim -p -e "DROP DATABASE IF EXISTS eclaim_db;"

# 3. Create new database
mysql -u eclaim -p -e "CREATE DATABASE eclaim_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 4. Import Schema V2
mysql -u eclaim -p eclaim_db < database/schema-mysql-merged.sql

# 5. Verify
mysql -u eclaim -p eclaim_db -e "SHOW TABLES;"
```

#### PostgreSQL:

```bash
# 1. Backup
pg_dump -U eclaim -d eclaim_db > backup_before_v2.sql

# 2. Drop existing database
psql -U eclaim -d postgres -c "DROP DATABASE IF EXISTS eclaim_db;"

# 3. Create new database
psql -U eclaim -d postgres -c "CREATE DATABASE eclaim_db;"

# 4. Import Schema V2
psql -U eclaim -d eclaim_db -f database/schema-postgresql-merged.sql

# 5. Verify
psql -U eclaim -d eclaim_db -c "\dt"
```

---

## ตรวจสอบหลัง Migration

### MySQL:

```bash
mysql -u eclaim -p eclaim_db
```

```sql
-- ตรวจสอบตารางที่สร้าง
SHOW TABLES;
-- คาดหวัง: eclaim_imported_files, claim_rep_opip_nhso_item, claim_rep_orf_nhso_item

-- ตรวจสอบ columns ใหม่
DESCRIBE claim_rep_opip_nhso_item;
-- ควรเห็น: file_id, row_number, his_matched, his_vn, reconcile_status

-- ตรวจสอบ Views
SHOW FULL TABLES WHERE table_type = 'VIEW';
-- คาดหวัง: v_daily_claim_summary, v_unmatched_claims, v_import_status
```

### PostgreSQL:

```bash
psql -U eclaim -d eclaim_db
```

```sql
-- ตรวจสอบตารางที่สร้าง
\dt

-- ตรวจสอบ columns
\d claim_rep_opip_nhso_item

-- ตรวจสอบ Views
\dv
```

---

## ทดสอบการ Import

### ผ่าน CLI:

```bash
# Import ไฟล์เดี่ยว
python eclaim_import.py downloads/eclaim_10670_OP_25690106_212004432.xls

# ตรวจสอบผลลัพธ์
mysql -u eclaim -p eclaim_db -e "
SELECT
    COUNT(*) as total_records,
    COUNT(DISTINCT file_id) as files_imported
FROM claim_rep_opip_nhso_item
WHERE file_id IS NOT NULL;
"
```

### ผ่าน Web UI:

1. เปิด http://localhost:5001/files
2. เลือก month/year
3. กด **"Import All"** หรือ import ทีละไฟล์
4. ดู real-time progress
5. ตรวจสอบ import status

---

## Rollback (ถ้าต้องการกลับไปเดิม)

```bash
# MySQL
mysql -u eclaim -p -e "DROP DATABASE IF EXISTS eclaim_db;"
mysql -u eclaim -p -e "CREATE DATABASE eclaim_db;"
mysql -u eclaim -p eclaim_db < backup_before_v2.sql

# PostgreSQL
psql -U eclaim -d postgres -c "DROP DATABASE IF EXISTS eclaim_db;"
psql -U eclaim -d postgres -c "CREATE DATABASE eclaim_db;"
psql -U eclaim -d eclaim_db < backup_before_v2.sql
```

---

## สิ่งที่ต้องรู้

### ✅ ข้อดี Schema V2:

1. **ใช้โครงสร้างเดิมของโรงพยาบาล** - ไม่ต้องเปลี่ยน field names
2. **เพิ่ม File Tracking** - รู้ว่า record มาจากไฟล์ไหน
3. **HIS Reconciliation Ready** - พร้อมสำหรับ reconcile
4. **UPSERT Support** - Import ซ้ำได้ไม่ duplicate
5. **รองรับ 2 DB** - MySQL และ PostgreSQL

### 📋 Column Mapping:

| Excel Column | Database Column |
|--------------|----------------|
| ชื่อ-สกุล | `name` |
| วันเข้ารักษา | `dateadm` |
| วันจำหน่าย | `datedsc` |
| ชดเชยสุทธิ (บาท) (สปสช.) | `reimb_nhso` |
| ชดเชยสุทธิ (บาท) (ต้นสังกัด) | `reimb_agency` |
| สิทธิหลัก | `main_inscl` |
| ประเภทผู้ป่วย | `ptype` |

ครบ **170+ columns!**

### 🔄 การใช้งานหลัง Migration:

**ทุกอย่างเหมือนเดิม!**
- ✅ Download ผ่าน Web UI
- ✅ Auto Schedule
- ✅ Import All
- ✅ Real-time Logs
- ✅ Settings Page

ไม่ต้องเปลี่ยนวิธีใช้งานอะไรเลย!

---

## Troubleshooting

### Error: Access denied

```bash
# ตรวจสอบ credentials ใน .env
cat .env | grep DB_

# หรือใช้ root user
mysql -u root -p
psql -U postgres
```

### Error: Table doesn't exist

```bash
# Re-import schema
mysql -u eclaim -p eclaim_db < database/schema-mysql-merged.sql
# หรือ
psql -U eclaim -d eclaim_db -f database/schema-postgresql-merged.sql
```

### Error: File already imported

```bash
# Check tracking table
mysql -u eclaim -p eclaim_db -e "SELECT * FROM eclaim_imported_files WHERE filename = 'your_file.xls';"

# ถ้าต้องการ import ซ้ำ, delete record:
mysql -u eclaim -p eclaim_db -e "DELETE FROM eclaim_imported_files WHERE filename = 'your_file.xls';"
```

---

## Support

หากมีปัญหา:
1. ตรวจสอบ logs: `docker-compose logs -f web`
2. ตรวจสอบ database connection ใน Settings page
3. ดู MIGRATION_GUIDE.md สำหรับรายละเอียดเพิ่มเติม

**Backup Location:** `backup_before_v2_*.sql` ในโฟลเดอร์ปัจจุบัน
