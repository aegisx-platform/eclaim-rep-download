# E-Claim Downloader & Data Import System

> โปรแกรมสำหรับ download และ import ข้อมูล e-claim จาก NHSO อัตโนมัติ พร้อม Web UI สำหรับจัดการไฟล์และนำเข้าฐานข้อมูล

![Dashboard](screenshots/dashboard.jpeg)

## ✨ Features

### 📥 E-Claim Downloader
- ✅ Login อัตโนมัติเข้าระบบ e-claim
- ✅ Download Excel files ทั้งหมดจากหน้า validation
- ✅ เลือก download ตามช่วงเดือน/ปี (Date Range Selection)
- ✅ Bulk download หลายเดือนพร้อมกัน
- ✅ เก็บประวัติการ download (ไม่ download ซ้ำ)
- ✅ ใช้ HTTP Client (requests) - เร็วและเบา ไม่ต้องเปิด browser
- ✅ Real-time progress tracking

### 🌐 Web UI Dashboard
- ✅ ดู dashboard สถิติไฟล์ที่ download
- ✅ จัดการไฟล์ (view, download, delete)
- ✅ Trigger download จาก Web UI
- ✅ เลือกช่วงวันที่สำหรับ bulk download
- ✅ Real-time progress แสดงสถานะการ download

### 💾 Database Import System
- ✅ Import ข้อมูล e-claim เข้า PostgreSQL/MySQL
- ✅ รองรับไฟล์ทุกประเภท: OP, IP, ORF, IP_APPEAL, IP_APPEAL_NHSO
- ✅ Auto-detect header row และ column mapping
- ✅ แปลงวันที่ไทย (BE) เป็น Gregorian calendar
- ✅ UPSERT support (ป้องกัน duplicate)
- ✅ HIS reconciliation fields (สำหรับ reconcile กับระบบโรงพยาบาล)
- ✅ CLI tool สำหรับ import file เดี่ยวหรือทั้ง directory
- ✅ Track import status (pending/processing/completed/failed)

### 🐳 Docker Support
- ✅ Docker Compose setup พร้อม PostgreSQL
- ✅ pgAdmin GUI สำหรับจัดการฐานข้อมูล
- ✅ Health checks และ auto-restart
- ✅ Volume persistence สำหรับข้อมูล
- ✅ Makefile สำหรับ commands ที่ง่ายต่อการใช้งาน

---

## 🚀 Quick Start (Docker)

### 1. Clone และ Setup

```bash
# Clone repository
git clone https://github.com/yourusername/eclaim-req-download.git
cd eclaim-req-download

# Setup environment
make setup

# Edit .env file
nano .env  # Update ECLAIM_USERNAME and ECLAIM_PASSWORD
```

### 2. Start Services

```bash
# Start all services (Flask + PostgreSQL + pgAdmin)
make up

# View logs
make logs
```

### 3. Access Services

- **Web UI**: http://localhost:5001
- **Database**: postgresql://eclaim:eclaim_password@localhost:5432/eclaim_db
- **pgAdmin**: http://localhost:5050 (admin@eclaim.local / admin)

---

## 📖 Manual Installation (Without Docker)

### Prerequisites

- Python 3.9+
- PostgreSQL 13+ (optional, for database import)

### Installation

1. Install Python dependencies:

```bash
pip install -r requirements.txt
```

2. Configure credentials:

```bash
cp .env.example .env
# Edit .env with your credentials
```

3. Setup database (optional):

```bash
# Create database
createdb eclaim_db

# Import schema
psql -U postgres -d eclaim_db -f database/schema.sql
```

### Run Web UI

```bash
export FLASK_APP=app.py
export FLASK_ENV=development
flask run --host=0.0.0.0 --port=5001
```

### Run Downloader CLI

```bash
# Download current month
python eclaim_downloader_http.py

# Download specific month/year
python eclaim_downloader_http.py --month 12 --year 2568

# Bulk download (multiple months)
python bulk_downloader.py 1,2568 12,2568
```

### Import to Database

```bash
# Import single file
python eclaim_import.py downloads/eclaim_10670_OP_25680122_205506156.xls

# Import all files in directory
python eclaim_import.py

# Analyze file structure
python eclaim_import.py --analyze downloads/file.xls
```

---

## 🐳 Docker Commands

For detailed Docker usage, see [DOCKER.md](DOCKER.md)

### Quick Commands

```bash
make setup      # Initial setup
make up         # Start services
make down       # Stop services
make logs       # View logs
make shell      # Access web container
make db-shell   # Access PostgreSQL
make import     # Import all files
make db-backup  # Backup database
```

---

## 📊 Database Schema

ระบบใช้ 3 ตารางหลัก:

1. **eclaim_imported_files** - Track import status
2. **eclaim_claims** - ข้อมูล OP/IP/Appeal claims
3. **eclaim_op_refer** - ข้อมูล OP Refer (ORF)

ดูรายละเอียดเพิ่มเติมใน [database/schema.sql](database/schema.sql)

### HIS Reconciliation

ระบบมี fields สำหรับ reconcile กับระบบโรงพยาบาล:

- `his_matched` - สถานะการ match
- `his_matched_at` - วันที่ match
- `his_vn` - Visit Number จากระบบ HIS
- `reconcile_status` - สถานะการ reconcile
- `reconcile_amount_diff` - ผลต่างยอดเงิน

---

## 📁 Project Structure

```
eclaim-req-download/
├── app.py                          # Flask web application
├── eclaim_downloader_http.py       # HTTP Client downloader
├── bulk_downloader.py              # Bulk download orchestrator
├── eclaim_import.py                # CLI import tool
├── docker-compose.yml              # Docker setup
├── Dockerfile                      # Docker image
├── Makefile                        # Easy commands
├── requirements.txt                # Python dependencies
│
├── config/
│   └── database.py                 # Database configuration
│
├── database/
│   ├── schema.sql                  # PostgreSQL schema
│   └── IMPORT_GUIDE.md             # Import documentation
│
├── utils/
│   ├── history_manager.py          # Download history
│   ├── file_manager.py             # File operations
│   ├── downloader_runner.py        # Background tasks
│   └── eclaim/
│       ├── parser.py               # XLS file parser
│       └── importer.py             # Database importer
│
├── templates/                      # HTML templates
│   ├── base.html
│   ├── dashboard.html
│   ├── files.html
│   └── download_config.html
│
├── static/                         # Static files
│   ├── css/
│   └── js/
│
├── downloads/                      # Downloaded files
├── logs/                           # Application logs
└── backups/                        # Database backups
```

---

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ECLAIM_USERNAME` | - | E-Claim login username |
| `ECLAIM_PASSWORD` | - | E-Claim login password |
| `DB_TYPE` | postgresql | Database type |
| `DB_HOST` | db | Database host |
| `DB_PORT` | 5432 | Database port |
| `DB_NAME` | eclaim_db | Database name |
| `DB_USER` | eclaim | Database user |
| `DB_PASSWORD` | eclaim_password | Database password |

---

## 📅 Automated Scheduling

### Linux/macOS - Cron Job

```bash
crontab -e
```

Run ทุกวันเวลา 9:00 น.:
```
0 9 * * * cd /path/to/eclaim-req-download && /usr/bin/python3 eclaim_downloader_http.py >> logs/cron.log 2>&1
```

### Windows - Task Scheduler

1. เปิด Task Scheduler
2. สร้าง Basic Task
3. ตั้งค่า Trigger (เช่น Daily 9:00 AM)
4. Action: Start a program
   - Program: `python.exe`
   - Arguments: `eclaim_downloader_http.py`
   - Start in: `C:\path\to\eclaim-req-download`

---

## 🧪 Testing

### Import Statistics (Sample)

- **Total Files**: 382 files
- **Total Records**: 40,006 records
- **Total Reimbursement**: ~141.6 million THB

**By Type:**
- OP: 252 files, 32,553 records (14.1M THB)
- IP: 82 files, 6,217 records (123.6M THB)
- ORF: 45 files, 260 records
- IP_APPEAL_NHSO: 2 files, 974 records (3.8M THB)
- IP_APPEAL: 1 file, 2 records (81K THB)

---

## 🐛 Troubleshooting

### Web UI Not Loading

```bash
# Check if containers are running
docker-compose ps

# Restart services
docker-compose restart

# View logs
docker-compose logs -f web
```

### Database Connection Failed

```bash
# Check database status
docker-compose ps db

# Restart database
docker-compose restart db
```

### Import Errors

```bash
# Check file structure
python eclaim_import.py --analyze downloads/file.xls

# View detailed logs
docker-compose logs -f web
```

For more details, see [DOCKER.md](DOCKER.md)

---

## 🔐 Security Notes

- ⚠️ **ห้าม commit `.env`** file ที่มี credentials
- ⚠️ เปลี่ยน default passwords ใน production
- ⚠️ ตั้งค่า file permissions ให้เหมาะสม
- ⚠️ ใช้ HTTPS สำหรับ production deployment

---

## 📚 Documentation

- [Docker Setup Guide](DOCKER.md) - Complete Docker documentation
- [Database Import Guide](database/IMPORT_GUIDE.md) - Import system documentation
- [E-Claim Analysis Report](ECLAIM_ANALYSIS_REPORT.md) - File structure analysis

---

## 👨‍💻 Developer

**Sathit Seethaphon**

If you find this project helpful, consider buying me a coffee! ☕

<script type="text/javascript" src="https://cdnjs.buymeacoffee.com/1.0.0/button.prod.min.js" data-name="bmc-button" data-slug="sathit" data-color="#FFDD00" data-emoji="☕"  data-font="Cookie" data-text="Buy me a coffee" data-outline-color="#000000" data-font-color="#000000" data-coffee-color="#ffffff" ></script>

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
- Docker Community

---

**Made with ❤️ in Thailand 🇹🇭**
