# 📱 Usage Guide

## Web UI Overview

Access the web interface at: **http://localhost:5001**

### Main Navigation

- **Dashboard** - สถิติและภาพรวม
- **Files** - จัดการไฟล์ที่ download
- **Download** - เลือกเดือน/ช่วงเวลาสำหรับ download
- **Settings** - ตั้งค่าระบบ

---

## 1. Dashboard Page

![Dashboard](../screenshots/dashboard.jpeg)

### Features

- ดูสถิติการ download (Total files, size, last run, file types)
- แสดงสถานะ **Auto Download Schedule** (Active/Inactive)
- แสดง **Next Download Time** ถ้าเปิด scheduler
- ดูไฟล์ล่าสุด 5 ไฟล์
- Real-time updates

### Quick Actions

- **Trigger Manual Download** - เริ่ม download ทันที
- **View All Files** - ไปยัง Files page
- **Configure Settings** - ไปยัง Settings page

---

## 2. Files Page

### Features

- ดูรายการไฟล์ทั้งหมด (pagination 50 ต่อหน้า)
- กรองตามเดือน/ปี (default: เดือนปัจจุบัน)
- แสดงสถานะ import (✅ Imported / ⏳ Pending)
- Download ไฟล์แต่ละไฟล์
- Import file เดี่ยว หรือ Import All
- Delete ไฟล์

### Month/Year Filter

```
เดือน: [มกราคม ▼] ปี: [2568 ▼] [Filter]
```

- เลือกเดือนและปีที่ต้องการ
- กด "Filter" เพื่อดูไฟล์ในช่วงนั้น
- กด "Clear" เพื่อดูทั้งหมด

### Import Actions

#### Import Single File

```
[ไฟล์] [Import] [Download] [Delete]
```

1. กด "Import" ที่ไฟล์ที่ต้องการ
2. รอ import เสร็จ (real-time progress)
3. สถานะเปลี่ยนเป็น "✅ Imported"

#### Import All Files

```
[Import All Pending Files]
```

1. กด "Import All" บนหน้า
2. ระบบจะ import ทุกไฟล์ที่ status = Pending
3. ดู progress bar แสดงความคืบหน้า
4. เสร็จแล้วแสดงจำนวนไฟล์ที่ import สำเร็จ

### Delete Files

```
[Delete] button ข้างแต่ละไฟล์
```

1. กด "Delete"
2. ยืนยันการลบ (confirmation dialog)
3. ไฟล์ถูกลบจากทั้ง disk และ database

---

## 3. Download Configuration Page

### Single Month Download

```
เลือกเดือน: [มกราคม ▼]
เลือกปี: [2568 ▼]
☐ Auto-import after download
[Download This Month]
```

**Steps:**
1. เลือก month และ year
2. เลือก "Auto-import" ถ้าต้องการ import ทันที
3. กด "Download This Month"
4. รอ download เสร็จ

**Use Case:** Download ข้อมูลเดือนที่พลาดไป

### Bulk Download (Date Range)

```
Start Date: [มกราคม ▼] [2568 ▼]
End Date: [ธันวาคม ▼] [2568 ▼]
☐ Auto-import after download
[Download All Months]
```

**Steps:**
1. เลือก start month/year
2. เลือก end month/year
3. เลือก "Auto-import" ถ้าต้องการ
4. กด "Download All Months"
5. ดู progress bar (แสดงเดือนที่กำลัง download)

**Estimated Time:**
- ~30-60 วินาทีต่อเดือน
- 12 เดือน ≈ 6-12 นาที

**Use Case:** Download ข้อมูลย้อนหลังทั้งปี

### Progress Display

```
Downloading: [██████████] 5/12 months
Current: December 2568
Files downloaded: 23 files
```

- แสดง progress bar
- แสดงเดือนที่กำลัง download
- แสดงจำนวนไฟล์

---

## 4. Settings Page

### E-Claim Credentials

```
Username: [_______________]
Password: [_______________]
[Save Credentials]
```

**Steps:**
1. ใส่ username และ password จาก NHSO
2. กด "Save Credentials"
3. ข้อมูลถูกเก็บใน `config/settings.json`

### Auto Download Schedule

```
☑ Enable Schedule

Scheduled Times:
• 09:00 [Remove]
• 20:00 [Remove]

[Add Schedule] Time: [HH:MM]

☑ Auto-import files after scheduled download

[Save Schedule] [Test Run Now]
```

**Setup Scheduler:**
1. กด **"Add Schedule"** และตั้งเวลา (เช่น 09:00)
2. เพิ่มเวลาอื่นๆ ได้ (เช่น 14:00, 20:00)
3. เลือก **"Auto-import"** ถ้าต้องการ
4. เปิด **"Enable Schedule"** toggle
5. กด **"Save Schedule"**

**Example:** ตั้งให้ download วันละ 3 ครั้ง
- 09:00 น. - download เช้า
- 14:00 น. - download บ่าย
- 20:00 น. - download เย็น

**Test Run:**
- กด **"Test Run Now"** เพื่อทดสอบทันที
- ไม่ต้องรอถึงเวลาที่ตั้งไว้

---

## ⏰ Using Auto Download Schedule

### Scheduler Overview

Scheduler จะ download ไฟล์ e-claim อัตโนมัติตามเวลาที่ตั้งไว้

### How It Works

1. **Background Service** - รันใน background
2. **Daily Execution** - download ตามเวลาที่ตั้ง
3. **Auto-Import** - import อัตโนมัติถ้าเปิดไว้
4. **Duplicate Prevention** - ไม่ download ซ้ำ

### Schedule Status Display

#### Dashboard Page

```
📅 Auto Download Schedule: Active
⏰ Next Download: Today at 20:00
```

#### Files Page

```
ℹ️ Auto Download is ACTIVE - Next run: Today at 20:00
```

### Checking Schedule Status

```bash
# API endpoint
curl http://localhost:5001/api/schedule
```

Response:
```json
{
  "enabled": true,
  "times": [
    {"hour": 9, "minute": 0},
    {"hour": 20, "minute": 0}
  ],
  "auto_import": true,
  "next_run_time": "2026-01-08T20:00:00"
}
```

### Managing Schedule

**Enable/Disable:**
- Settings page → Toggle "Enable Schedule"
- กด "Save Schedule"

**Add Time:**
- Settings page → "Add Schedule"
- เลือกเวลา → กด "Add"

**Remove Time:**
- Settings page → กด "Remove" ข้างเวลาที่ต้องการลบ

**Test Immediately:**
- Settings page → กด "Test Run Now"

### Troubleshooting Scheduler

**Scheduler ไม่ทำงาน:**
```bash
# ตรวจสอบ logs
docker-compose logs -f web | grep scheduler

# Restart service
docker-compose restart web
```

**เปลี่ยนเวลาแล้วไม่ update:**
- ให้ restart web service
```bash
docker-compose restart web
```

---

## 📋 Real-time Log Viewer

### Viewing Logs

**Web UI:**
- กด "View Logs" button ที่ Dashboard หรือ Files page
- Real-time streaming (Server-Sent Events)

**Docker:**
```bash
# View all logs
docker-compose logs -f

# View web logs only
docker-compose logs -f web

# View last 100 lines
docker-compose logs --tail=100 web
```

### Log Files

```
logs/
├── downloader.log      # Download logs
├── import.log          # Import logs
└── app.log             # Application logs
```

---

## 🔄 Import System

### Import Process

1. **Parse Excel** - อ่านไฟล์ .xls
2. **Extract Data** - แยกข้อมูลตาม columns
3. **Transform** - แปลงวันที่, ตรวจสอบข้อมูล
4. **Load** - import เข้า database (UPSERT)
5. **Track Status** - บันทึกสถานะ

### Import Status

- ✅ **Imported** - import สำเร็จแล้ว
- ⏳ **Pending** - ยังไม่ได้ import
- ❌ **Failed** - import ไม่สำเร็จ

### Re-import Files

ถ้าต้องการ import ซ้ำ:

```bash
# ลบ tracking record
docker-compose exec db psql -U eclaim -d eclaim_db -c \
  "DELETE FROM eclaim_imported_files WHERE filename = 'your_file.xls';"

# Import ใหม่
docker-compose exec web python eclaim_import.py downloads/your_file.xls
```

---

## 🎯 Best Practices

### Daily Operations

1. **Check Dashboard** ทุกเช้า
   - ดูสถานะ scheduler
   - ตรวจสอบไฟล์ใหม่

2. **Review Import Status** สัปดาห์ละครั้ง
   - ตรวจสอบ pending files
   - Import ไฟล์ที่ค้างอยู่

3. **Monitor Logs** เมื่อมีปัญหา
   - ดู error messages
   - ตรวจสอบ download/import failures

### Monthly Tasks

1. **Backup Database**
   ```bash
   docker-compose exec db pg_dump -U eclaim eclaim_db > backup_$(date +%Y%m).sql
   ```

2. **Review Statistics**
   - ดูจำนวนไฟล์ทั้งหมด
   - ตรวจสอบความถูกต้อง

3. **Clean Old Files** (optional)
   ```bash
   # Keep only last 3 months
   find downloads/ -name "*.xls" -mtime +90 -delete
   ```

---

**[← Back: Configuration](CONFIGURATION.md)** | **[Next: Database Guide →](DATABASE.md)**
