# ✨ Features

## 🌐 Web UI Dashboard

- ✅ **Dashboard** - สถิติไฟล์ที่ download พร้อม charts
- ✅ **Files Management** - จัดการไฟล์ (view, download, delete)
- ✅ **Pagination** - แสดง 50 ไฟล์ต่อหน้า พร้อม smart navigation
- ✅ **Month/Year Filter** - กรองไฟล์ตามเดือน/ปี (default: เดือนปัจจุบัน)
- ✅ **Import Status** - แสดงสถานะ imported/pending ของแต่ละไฟล์
- ✅ **Import All** - import ไฟล์ทั้งหมดที่ pending ได้ครั้งเดียว
- ✅ **Clear All Data** - ลบข้อมูลทั้งหมด (with triple confirmation)
- ✅ **Settings Page** - ตั้งค่า username/password จาก UI
- ✅ **Real-time Log Viewer** - ดู download/import progress แบบ real-time

## 📥 Download System

- ✅ **Auto Login** - เข้าสู่ระบบ e-claim อัตโนมัติ
- ✅ **HTTP Client** - ใช้ requests library (เร็ว ไม่ต้องเปิด browser)
- ✅ **Single Month Download** - download เดือน/ปีที่ต้องการ
- ✅ **Bulk Download** - download หลายเดือนพร้อมกัน (sequential processing)
- ✅ **Date Range Selection** - เลือกช่วงเวลา start/end date
- ✅ **Auto-Import Toggle** - เลือกว่าจะ import หลัง download หรือไม่
- ✅ **Duplicate Prevention** - ไม่ download ซ้ำ (check history)
- ✅ **Progress Tracking** - แสดง progress bar แบบ real-time
- ✅ **Download History** - เก็บประวัติการ download ทั้งหมด

## ⏰ Automated Scheduling

- ✅ **Multiple Schedules** - ตั้งเวลา download ได้หลายช่วงต่อวัน (เช่น 09:00, 14:00, 20:00)
- ✅ **Enable/Disable Toggle** - เปิด/ปิด scheduler จาก Web UI
- ✅ **Auto-Import Option** - เลือกให้ import อัตโนมัติหลัง scheduled download
- ✅ **Schedule Status Display** - แสดงสถานะ scheduler บน Dashboard และ Files page
- ✅ **Next Run Time** - แสดงเวลาที่จะ download ครั้งถัดไป
- ✅ **Test Run** - ทดสอบ download ทันทีโดยไม่ต้องรอถึงเวลา
- ✅ **Background Execution** - รันใน background ไม่กระทบการใช้งาน
- ✅ **Persistent Settings** - บันทึกการตั้งค่าใน config/settings.json

## 💾 Database Import System

- ✅ **Multi-Database Support** - รองรับ PostgreSQL และ MySQL
- ✅ **Hospital Schema Compatible** - ใช้โครงสร้างตารางของโรงพยาบาลเป็นหลัก
- ✅ **Complete Field Mapping** - Map ทุก columns จาก Excel (170+ fields)
- ✅ **All File Types** - OP, IP, ORF, IP_APPEAL, IP_APPEAL_NHSO
- ✅ **Smart Header Detection** - หา header row อัตโนมัติ
- ✅ **Date Conversion** - แปลงวันที่ไทย (dd/mm/yyyy) เป็น timestamp
- ✅ **Data Validation** - ตรวจสอบ data types และ truncate strings
- ✅ **UPSERT Logic** - ป้องกัน duplicate records
- ✅ **Concurrent Import** - import ทันทีหลัง download แต่ละไฟล์
- ✅ **Import Tracking** - track สถานะการ import ของแต่ละไฟล์
- ✅ **HIS Reconciliation Fields** - fields สำหรับ reconcile กับระบบ HIS
- ✅ **CLI Tool** - import จาก command line ได้

## 🐳 Docker Deployment

- ✅ **Two Deployment Modes:**
  - `docker-compose.yml` - Full stack (Web + PostgreSQL + pgAdmin)
  - `docker-compose-mysql.yml` - Full stack with MySQL
  - `docker-compose-no-db.yml` - Download only (ไม่มี database)
- ✅ **Optimized Dockerfile** - Python 3.12 with multi-stage builds
- ✅ **Health Checks** - ตรวจสอบสถานะ services อัตโนมัติ
- ✅ **Auto-Restart** - restart service เมื่อมีปัญหา
- ✅ **Volume Persistence** - เก็บข้อมูลถาวร (downloads, logs, database)
- ✅ **Environment Configuration** - ตั้งค่าผ่าน .env file
- ✅ **Timezone Support** - Bangkok timezone (GMT+7)
- ✅ **One-Command Deploy** - `docker-compose up -d`
- ✅ **Database Auto-Initialization** - Schema ถูกสร้างอัตโนมัติตอน first run

---

**[← Back to Main README](../README.md)**
