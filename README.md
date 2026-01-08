# E-Claim Downloader & Data Import System

> ระบบ download และ import ข้อมูล e-claim จาก NHSO อัตโนมัติ พร้อม Web UI สำหรับจัดการไฟล์และนำเข้าฐานข้อมูล

![Dashboard](screenshots/dashboard.jpeg)

---

## ☕ Support This Project

If you find this project helpful, consider buying me a coffee!

<a href="https://www.buymeacoffee.com/sathit" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

**Developer:** Sathit Seethaphon | [aegisx platform](https://github.com/aegisx-platform)

---

## ✨ Features

### 🌐 Web UI Dashboard
- ✅ **Dashboard** - สถิติไฟล์ที่ download พร้อม charts
- ✅ **Files Management** - จัดการไฟล์ (view, download, delete)
- ✅ **Pagination** - แสดง 50 ไฟล์ต่อหน้า พร้อม smart navigation
- ✅ **Month/Year Filter** - กรองไฟล์ตามเดือน/ปี (default: เดือนปัจจุบัน)
- ✅ **Import Status** - แสดงสถานะ imported/pending ของแต่ละไฟล์
- ✅ **Import All** - import ไฟล์ทั้งหมดที่ pending ได้ครั้งเดียว
- ✅ **Clear All Data** - ลบข้อมูลทั้งหมด (with triple confirmation)
- ✅ **Settings Page** - ตั้งค่า username/password จาก UI
- ✅ **Real-time Log Viewer** - ดู download/import progress แบบ real-time

### 📥 Download System
- ✅ **Auto Login** - เข้าสู่ระบบ e-claim อัตโนมัติ
- ✅ **HTTP Client** - ใช้ requests library (เร็ว ไม่ต้องเปิด browser)
- ✅ **Single Month Download** - download เดือน/ปีที่ต้องการ
- ✅ **Bulk Download** - download หลายเดือนพร้อมกัน (sequential processing)
- ✅ **Date Range Selection** - เลือกช่วงเวลา start/end date
- ✅ **Auto-Import Toggle** - เลือกว่าจะ import หลัง download หรือไม่
- ✅ **Duplicate Prevention** - ไม่ download ซ้ำ (check history)
- ✅ **Progress Tracking** - แสดง progress bar แบบ real-time
- ✅ **Download History** - เก็บประวัติการ download ทั้งหมด

### ⏰ Automated Scheduling
- ✅ **Multiple Schedules** - ตั้งเวลา download ได้หลายช่วงต่อวัน (เช่น 09:00, 14:00, 20:00)
- ✅ **Enable/Disable Toggle** - เปิด/ปิด scheduler จาก Web UI
- ✅ **Auto-Import Option** - เลือกให้ import อัตโนมัติหลัง scheduled download
- ✅ **Schedule Status Display** - แสดงสถานะ scheduler บน Dashboard และ Files page
- ✅ **Next Run Time** - แสดงเวลาที่จะ download ครั้งถัดไป
- ✅ **Test Run** - ทดสอบ download ทันทีโดยไม่ต้องรอถึงเวลา
- ✅ **Background Execution** - รันใน background ไม่กระทบการใช้งาน
- ✅ **Persistent Settings** - บันทึกการตั้งค่าใน config/settings.json

### 💾 Database Import System
- ✅ **Multi-Database Support** - รองรับ PostgreSQL และ MySQL
- ✅ **All File Types** - OP, IP, ORF, IP_APPEAL, IP_APPEAL_NHSO
- ✅ **Smart Header Detection** - หา header row อัตโนมัติ
- ✅ **Column Auto-Mapping** - map columns ตาม field names
- ✅ **Date Conversion** - แปลงวันที่ไทย (BE) เป็น Gregorian (AD)
- ✅ **UPSERT Logic** - ป้องกัน duplicate records
- ✅ **Concurrent Import** - import ทันทีหลัง download แต่ละไฟล์
- ✅ **Import Tracking** - track สถานะการ import ของแต่ละไฟล์
- ✅ **HIS Reconciliation Fields** - fields สำหรับ reconcile กับระบบ HIS
- ✅ **CLI Tool** - import จาก command line ได้

### 🐳 Docker Deployment
- ✅ **Two Deployment Modes:**
  - `docker-compose.yml` - Full stack (Web + PostgreSQL + pgAdmin)
  - `docker-compose-no-db.yml` - Download only (ไม่มี database)
- ✅ **Optimized Dockerfile** - Python 3.12 with multi-stage builds
- ✅ **Health Checks** - ตรวจสอบสถานะ services อัตโนมัติ
- ✅ **Auto-Restart** - restart service เมื่อมีปัญหา
- ✅ **Volume Persistence** - เก็บข้อมูลถาวร (downloads, logs, database)
- ✅ **Environment Configuration** - ตั้งค่าผ่าน .env file
- ✅ **Timezone Support** - Bangkok timezone (GMT+7)
- ✅ **One-Command Deploy** - `docker-compose up -d`

---

## 🚀 Quick Start

### Docker Deployment (แนะนำ)

#### แบบที่ 1: Full Stack (มี Database) 🏥

เหมาะสำหรับใช้งานจริงในโรงพยาบาล มีทั้ง download และ import เข้า database

```bash
# 1. Clone repository
git clone https://github.com/aegisx-platform/eclaim-req-download.git
cd eclaim-req-download

# 2. Setup environment
cp .env.example .env
nano .env  # แก้ไข ECLAIM_USERNAME และ ECLAIM_PASSWORD

# 3. Start all services
docker-compose up -d

# 4. Check logs
docker-compose logs -f
```

**เข้าใช้งาน:**
- 🌐 **Web UI**: http://localhost:5001
- 🗄️ **Database**: postgresql://eclaim:eclaim_password@localhost:5432/eclaim_db
- 🔧 **pgAdmin**: http://localhost:5050 (admin@eclaim.local / admin)

#### แบบที่ 2: Download Only (ไม่มี Database) 📥

เหมาะสำหรับ download ไฟล์อย่างเดียว ไม่ต้องการ import เข้า database

```bash
# 1-2. เหมือนแบบที่ 1

# 3. Start web service only
docker-compose -f docker-compose-no-db.yml up -d

# 4. Check logs
docker-compose -f docker-compose-no-db.yml logs -f
```

**เข้าใช้งาน:**
- 🌐 **Web UI**: http://localhost:5001

### Manual Installation (Without Docker)

<details>
<summary>คลิกเพื่อดูวิธี install แบบ manual</summary>

**Prerequisites:**
- Python 3.12+
- PostgreSQL 13+ (optional)

**Installation:**

```bash
# 1. Clone repository
git clone https://github.com/aegisx-platform/eclaim-req-download.git
cd eclaim-req-download

# 2. Create virtual environment
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure credentials
cp .env.example .env
nano .env  # Update credentials

# 5. (Optional) Setup database
createdb eclaim_db
psql -U postgres -d eclaim_db -f database/schema.sql

# 6. Run Flask app
python app.py
```

**Access:** http://localhost:5001

</details>

---

## 📱 Web UI Guide

### 1. Dashboard Page
- ดูสถิติการ download (Total files, size, last run, file types)
- แสดงสถานะ **Auto Download Schedule** (Active/Inactive)
- แสดง **Next Download Time** ถ้าเปิด scheduler
- ดูไฟล์ล่าสุด 5 ไฟล์

### 2. Files Page
- ดูรายการไฟล์ทั้งหมด (pagination 50 ต่อหน้า)
- กรองตามเดือน/ปี (default: เดือนปัจจุบัน)
- แสดงสถานะ import (Imported/Pending)
- Download ไฟล์แต่ละไฟล์
- Import file เดี่ยว หรือ Import All
- Delete ไฟล์

### 3. Date Range Page
- **Single Month Download** - เลือก month/year และ download
- **Bulk Download** - เลือกช่วงเวลา start/end แล้ว download ทั้งหมด
- **Auto-Import Checkbox** - เลือกว่าจะ import หรือไม่
- ดู estimated time

### 4. Settings Page
- **E-Claim Credentials** - ตั้งค่า username/password
- **Auto Download Schedule:**
  - Add/Remove scheduled times
  - Enable/Disable scheduler
  - Auto-import toggle สำหรับ scheduled downloads
  - ดูสถานะ scheduled jobs
  - Test Run Now button

---

## ⏰ Using Auto Download Schedule

### ตั้งค่า Scheduler

1. ไปที่ **Settings** page
2. เลื่อนลงไปส่วน "Auto Download Schedule"
3. กด **"Add Schedule"** และตั้งเวลา (เช่น 09:00)
4. เพิ่มเวลาอื่นๆ ได้ (เช่น 14:00, 20:00)
5. เลือก **"Auto-import files after download"** ถ้าต้องการ
6. เปิด **"Enable Schedule"** toggle
7. กด **"Save Schedule"**

**ตัวอย่าง:** ตั้งให้ download วันละ 2 ครั้ง
- 09:00 น. - download เช้า
- 20:00 น. - download เย็น

### ตรวจสอบสถานะ

- **Dashboard Page** - ดูสถานะ scheduler และ next run time
- **Files Page** - แสดง banner บอกสถานะ scheduler
- **Settings Page** - ดู scheduled jobs ทั้งหมด

---

## 🔧 Configuration

### Settings File (config/settings.json)

ระบบใช้ไฟล์ `config/settings.json` เก็บการตั้งค่า (สามารถแก้ไขผ่าน Web UI ได้):

```json
{
  "eclaim_username": "your_username",
  "eclaim_password": "your_password",
  "download_dir": "downloads",
  "auto_import_default": false,
  "schedule_enabled": true,
  "schedule_times": [
    {"hour": 9, "minute": 0},
    {"hour": 20, "minute": 0}
  ],
  "schedule_auto_import": true
}
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ECLAIM_USERNAME` | - | E-Claim login username |
| `ECLAIM_PASSWORD` | - | E-Claim login password |
| `DB_TYPE` | postgresql | Database type (postgresql/mysql/none) |
| `DB_HOST` | db | Database host |
| `DB_PORT` | 5432 | Database port |
| `DB_NAME` | eclaim_db | Database name |
| `DB_USER` | eclaim | Database user |
| `DB_PASSWORD` | eclaim_password | Database password |
| `TZ` | Asia/Bangkok | Timezone |
| `FLASK_ENV` | production | Flask environment |

**Priority:** `config/settings.json` > Environment Variables

---

## 📁 Project Structure

```
eclaim-req-download/
├── app.py                          # Flask web application
├── eclaim_downloader_http.py       # HTTP Client downloader
├── bulk_downloader.py              # Bulk download orchestrator
├── download_with_import.py         # Download wrapper with import
├── eclaim_import.py                # CLI import tool
├── Dockerfile                      # Docker image definition
├── docker-compose.yml              # Full stack deployment
├── docker-compose-no-db.yml        # Download-only deployment
├── .env.example                    # Environment template
├── .dockerignore                   # Docker build optimization
├── requirements.txt                # Python dependencies
│
├── config/
│   ├── database.py                 # Database configuration
│   ├── settings.json.example       # Settings template
│   └── settings.json               # User settings (gitignored)
│
├── database/
│   ├── schema.sql                  # PostgreSQL schema
│   └── IMPORT_GUIDE.md             # Import documentation
│
├── utils/
│   ├── __init__.py
│   ├── history_manager.py          # Download history CRUD
│   ├── file_manager.py             # Safe file operations
│   ├── downloader_runner.py        # Background process management
│   ├── import_runner.py            # Import process management
│   ├── log_stream.py               # Real-time log streaming (SSE)
│   ├── settings_manager.py         # Settings CRUD
│   ├── scheduler.py                # APScheduler integration
│   └── eclaim/
│       ├── parser.py               # XLS file parser
│       └── importer.py             # Database importer
│
├── templates/                      # Jinja2 HTML templates
│   ├── base.html                   # Base template with navbar
│   ├── dashboard.html              # Dashboard with stats
│   ├── files.html                  # File list with pagination
│   ├── download_config.html        # Date range selection
│   ├── settings.html               # Settings configuration
│   └── components/
│       └── log_viewer.html         # Real-time log component
│
├── static/                         # Static assets
│   ├── js/
│   │   └── app.js                  # Frontend JavaScript
│   └── css/
│       └── custom.css              # Custom styles
│
├── downloads/                      # Downloaded Excel files
├── logs/                           # Application logs
└── backups/                        # Database backups
```

---

## 📊 Database Schema

### Tables

1. **eclaim_imported_files**
   - Track import status ของแต่ละไฟล์
   - Fields: file_id, filename, file_hash, imported_at, import_status

2. **eclaim_claims**
   - ข้อมูล claims ทุกประเภท (OP, IP, IP_APPEAL, IP_APPEAL_NHSO)
   - Fields: claim_id, claim_type, hn, pid, vn, admission_date, discharge_date, total_amount
   - HIS reconciliation fields: his_matched, his_vn, reconcile_status

3. **eclaim_op_refer**
   - ข้อมูล OP Refer (ORF)
   - Fields: refer_id, hn, pid, refer_date, refer_to_hcode

### HIS Reconciliation Fields

ระบบมี fields สำหรับ reconcile กับระบบโรงพยาบาล:
- `his_matched` - สถานะการ match (boolean)
- `his_matched_at` - วันเวลาที่ match
- `his_vn` - Visit Number จากระบบ HIS
- `reconcile_status` - สถานะ (matched/unmatched/conflict)
- `reconcile_amount_diff` - ผลต่างยอดเงิน (e-claim vs HIS)

ดูรายละเอียดเพิ่มเติม: [database/schema.sql](database/schema.sql)

---

## ⚖️ Legal & Compliance

### ✅ การใช้งานที่ถูกต้องตามกฎหมาย

โปรแกรมนี้**ไม่ผิดกฎหมาย** เมื่อใช้งานอย่างถูกต้อง เพราะ:

1. **ใช้ Credentials ที่ได้รับอนุญาต**
   - โรงพยาบาลได้รับ username/password จาก NHSO อย่างถูกต้อง
   - ไม่มีการ hack หรือเข้าถึงระบบโดยไม่ได้รับอนุญาต

2. **เข้าถึงข้อมูลที่มีสิทธิ์**
   - ดึงเฉพาะข้อมูลที่โรงพยาบาลสามารถเข้าถึงได้ผ่าน e-claim
   - ไม่มีการ bypass security หรือเข้าถึงข้อมูลของหน่วยงานอื่น

3. **ใช้ตามวัตถุประสงค์ที่ถูกต้อง**
   - จัดการข้อมูลการเบิกจ่ายของโรงพยาบาลเอง
   - Reconcile กับระบบ HIS
   - Audit และ reporting

### ⚠️ พ.ร.บ. คุ้มครองข้อมูลส่วนบุคคล (PDPA)

ข้อมูล e-claim มี**ข้อมูลส่วนบุคคลของผู้ป่วย** (HN, CID, ชื่อ-นามสกุล, การวินิจฉัย)

**ข้อปฏิบัติที่ต้อง comply:**

1. **ฐานกฎหมายในการประมวลผล**
   - โรงพยาบาลมีฐานกฎหมาย (ปฏิบัติตามสัญญา, หน้าที่ตามกฎหมาย)
   - ใช้เพื่อการรักษาพยาบาล บริหารจัดการ และการเบิกจ่าย

2. **รักษาความมั่นคงปลอดภัย**
   - ตั้งรหัสผ่าน database ที่แข็งแรง
   - เข้าถึงได้เฉพาะบุคลากรที่ได้รับอนุญาต
   - ใช้ VPN หรือ private network เท่านั้น
   - **ห้ามเปิด public internet โดยเด็ดขาด**

3. **จำกัดการเข้าถึง (Access Control)**
   - ตั้งค่า firewall ให้เข้าถึงได้เฉพาะ IP ภายในโรงพยาบาล
   - พิจารณาเพิ่ม authentication (username/password login)
   - Audit logs ทุกการเข้าถึง

4. **การเก็บรักษาและลบทิ้ง**
   - เก็บข้อมูลเท่าที่จำเป็น (ตามระเบียบ NHSO)
   - ลบข้อมูลเมื่อหมดความจำเป็น
   - Backup ต้องเข้ารหัส

5. **ห้ามแชร์หรือเปิดเผย**
   - ห้ามส่งข้อมูลออกนอกโรงพยาบาล
   - ห้ามแชร์ไฟล์ผ่าน cloud storage สาธารณะ
   - ห้าม export ข้อมูลผู้ป่วยไปใช้นอกวัตถุประสงค์

### ❌ การใช้งานที่ไม่เหมาะสม

**ห้าม** ใช้โปรแกรมนี้เพื่อ:
- ❌ ขายหรือแชร์ข้อมูลผู้ป่วยให้บุคคลภายนอก
- ❌ ใช้ข้อมูลนอกวัตถุประสงค์ (การตลาด, วิจัยโดยไม่ได้รับความยินยอม)
- ❌ เปิดเผยข้อมูลส่วนบุคคลโดยไม่ได้รับอนุญาต
- ❌ Deploy บน public cloud โดยไม่มีมาตรการรักษาความปลอดภัย

### Disclaimer

```
โปรแกรมนี้พัฒนาเพื่อช่วยโรงพยาบาลในการจัดการข้อมูล e-claim

ผู้พัฒนาไม่รับผิดชอบต่อ:
- การใช้งานที่ไม่ถูกต้องตามกฎหมาย
- ความเสียหายจากการรั่วไหลของข้อมูล
- การละเมิด PDPA หรือกฎหมายอื่นๆ

ผู้ใช้งานต้องรับผิดชอบในการ:
- ตรวจสอบความถูกต้องของข้อมูล
- ปฏิบัติตาม PDPA และกฎหมายที่เกี่ยวข้อง
- รักษาความปลอดภัยของข้อมูลผู้ป่วย
```

---

## 🔐 Security Best Practices

### Production Deployment Checklist

- [ ] เปลี่ยน default passwords ทั้งหมด
- [ ] ตั้งค่า firewall จำกัดการเข้าถึง
- [ ] ใช้ VPN สำหรับ remote access
- [ ] เปิด HTTPS (SSL/TLS certificate)
- [ ] เพิ่ม authentication สำหรับ Web UI
- [ ] เข้ารหัส database backups
- [ ] ตั้งค่า audit logging
- [ ] Monitor logs เป็นประจำ
- [ ] Update security patches สม่ำเสมอ

### Network Security

```bash
# Allow access only from hospital network
ufw allow from 192.168.1.0/24 to any port 5001

# Block all other access
ufw deny 5001
```

### Authentication (Recommended)

พิจารณาเพิ่ม:
- Login system สำหรับ Web UI
- OAuth/LDAP integration กับระบบโรงพยาบาล
- Two-factor authentication (2FA)
- Session timeout
- Role-based access control (RBAC)

### Data Encryption

- **Database**: ใช้ PostgreSQL encryption at rest
- **Backups**: เข้ารหัส backup files
- **Connection**: ใช้ SSL/TLS สำหรับ database connection
- **Credentials**: ไม่เก็บ plain text passwords

---

## 🐛 Troubleshooting

### Web UI ไม่โหลด

```bash
# ตรวจสอบ containers
docker-compose ps

# Restart services
docker-compose restart

# ดู logs
docker-compose logs -f web
```

### Database เชื่อมต่อไม่ได้

```bash
# ตรวจสอบ database
docker-compose ps db

# Restart database
docker-compose restart db

# ทดสอบ connection
docker-compose exec web python -c "from config.database import get_db_config; print(get_db_config())"
```

### Import มีปัญหา

```bash
# วิเคราะห์โครงสร้างไฟล์
python eclaim_import.py --analyze downloads/file.xls

# ดู logs
docker-compose logs -f web

# ตรวจสอบ database schema
docker-compose exec db psql -U eclaim -d eclaim_db -c "\dt"
```

### Scheduler ไม่ทำงาน

```bash
# ตรวจสอบ settings
curl http://localhost:5001/api/schedule | python3 -m json.tool

# Restart web service
docker-compose restart web

# ดู logs
docker-compose logs -f web | grep scheduler
```

---

## 🧪 Sample Statistics

จากการทดสอบจริง:

- **Total Files**: 382 ไฟล์
- **Total Records**: 40,006 records
- **Total Reimbursement**: ~141.6 million THB

**By Type:**
- **OP**: 252 files, 32,553 records (14.1M THB)
- **IP**: 82 files, 6,217 records (123.6M THB)
- **ORF**: 45 files, 260 records
- **IP_APPEAL_NHSO**: 2 files, 974 records (3.8M THB)
- **IP_APPEAL**: 1 file, 2 records (81K THB)

---

## 📚 Documentation

- 🐳 [Docker Setup Guide](DOCKER.md) - Complete Docker documentation
- 💾 [Database Import Guide](database/IMPORT_GUIDE.md) - Import system documentation
- 📊 [E-Claim Analysis Report](ECLAIM_ANALYSIS_REPORT.md) - File structure analysis

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📝 License

MIT License - see [LICENSE](LICENSE) file for details

---

## 🙏 Acknowledgments

- NHSO E-Claim System
- Flask Framework
- PostgreSQL Database
- APScheduler Library
- Tailwind CSS
- Docker Community

---

## 🏷️ Version History

### v1.1.0 (2026-01-08)
- ✨ Auto Download Scheduling with APScheduler
- ✨ Settings Page (Credentials + Schedule Management)
- ✨ Pagination & Month/Year Filtering
- ✨ Real-time Log Streaming (Server-Sent Events)
- ✨ Schedule Status Display
- ✨ Auto-Import Toggles
- 🐳 Docker Compose (with/without DB)
- 📚 Legal & Compliance Documentation

### v1.0.0 (Initial Release)
- 📥 E-Claim Downloader (HTTP Client)
- 🌐 Web UI Dashboard
- 💾 Database Import System
- 🐳 Docker Support

---

**Made with ❤️ by [aegisx platform](https://github.com/aegisx-platform)**
