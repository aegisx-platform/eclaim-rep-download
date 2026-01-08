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
- ✅ จัดการไฟล์ (view, download, delete) พร้อม pagination
- ✅ Trigger download จาก Web UI
- ✅ เลือกช่วงวันที่สำหรับ bulk download
- ✅ Real-time progress และ log streaming
- ✅ Auto-import toggle สำหรับแต่ละการ download
- ✅ Filter files ตาม month/year
- ✅ Settings page สำหรับ credentials management

### ⏰ Automated Scheduling
- ✅ ตั้งเวลา download อัตโนมัติได้หลายช่วงต่อวัน
- ✅ Enable/Disable scheduler จาก Web UI
- ✅ Auto-import option สำหรับ scheduled downloads
- ✅ แสดงสถานะ scheduler และ next run time
- ✅ Test run สำหรับทดสอบทันที

### 💾 Database Import System
- ✅ Import ข้อมูล e-claim เข้า PostgreSQL/MySQL
- ✅ รองรับไฟล์ทุกประเภท: OP, IP, ORF, IP_APPEAL, IP_APPEAL_NHSO
- ✅ Auto-detect header row และ column mapping
- ✅ แปลงวันที่ไทย (BE) เป็น Gregorian calendar
- ✅ UPSERT support (ป้องกัน duplicate)
- ✅ HIS reconciliation fields (สำหรับ reconcile กับระบบโรงพยาบาล)
- ✅ CLI tool สำหรับ import file เดี่ยวหรือทั้ง directory
- ✅ Track import status (pending/processing/completed/failed)
- ✅ Auto-import ทันทีหลัง download (configurable)

### 🐳 Docker Support
- ✅ Docker Compose แบบมี Database (PostgreSQL + pgAdmin)
- ✅ Docker Compose แบบไม่มี Database (Download อย่างเดียว)
- ✅ Health checks และ auto-restart
- ✅ Volume persistence สำหรับข้อมูล
- ✅ Environment-based configuration
- ✅ One-command deployment

---

## 🚀 Quick Start (Docker)

### แบบที่ 1: มี Database (Full Features)

เหมาะสำหรับใช้งานจริง มีทั้ง download และ import เข้า database

```bash
# 1. Clone repository
git clone https://github.com/aegisx-platform/eclaim-req-download.git
cd eclaim-req-download

# 2. Copy environment file
cp .env.example .env

# 3. Edit credentials
nano .env  # Update ECLAIM_USERNAME and ECLAIM_PASSWORD

# 4. Start services (Web + Database + pgAdmin)
docker-compose up -d

# 5. View logs
docker-compose logs -f
```

**Access:**
- **Web UI**: http://localhost:5001
- **Database**: postgresql://eclaim:eclaim_password@localhost:5432/eclaim_db
- **pgAdmin**: http://localhost:5050 (admin@eclaim.local / admin)

### แบบที่ 2: ไม่มี Database (Download Only)

เหมาะสำหรับ download ไฟล์อย่างเดียว ไม่ต้องการ import

```bash
# 1-3. เหมือนแบบที่ 1

# 4. Start services (Web Only - No Database)
docker-compose -f docker-compose-no-db.yml up -d

# 5. View logs
docker-compose -f docker-compose-no-db.yml logs -f
```

**Access:**
- **Web UI**: http://localhost:5001

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
- ⚠️ จำกัดการเข้าถึง Web UI เฉพาะเครือข่ายภายใน
- ⚠️ Encrypt database backups
- ⚠️ ตรวจสอบ logs เป็นประจำ

---

## ⚖️ Legal & Compliance (ข้อกฎหมายและการปฏิบัติตาม)

### การใช้งานที่ถูกต้องตามกฎหมาย ✅

โปรแกรมนี้**ไม่ผิดกฎหมาย** เมื่อใช้งานอย่างถูกต้อง เพราะ:

1. **ใช้ Credentials ที่ถูกต้อง**
   - โรงพยาบาลได้รับ username/password จาก NHSO อย่างถูกต้องตามกฎหมาย
   - ไม่มีการ hack หรือเข้าถึงระบบโดยไม่ได้รับอนุญาต

2. **เข้าถึงข้อมูลที่มีสิทธิ์**
   - ดึงเฉพาะข้อมูลที่โรงพยาบาลสามารถเข้าถึงได้อยู่แล้วผ่านระบบ e-claim
   - ไม่มีการ bypass security หรือเข้าถึงข้อมูลของหน่วยงานอื่น

3. **ใช้งานตามวัตถุประสงค์ที่ถูกต้อง**
   - จัดการข้อมูลการเบิกจ่ายของโรงพยาบาลเอง
   - ใช้ในการ reconcile กับระบบ HIS
   - ใช้ในการตรวจสอบและ audit

### พ.ร.บ. คุ้มครองข้อมูลส่วนบุคคล (PDPA) ⚠️

ข้อมูล e-claim มี**ข้อมูลส่วนบุคคลของผู้ป่วย** (HN, CID, ชื่อ-นามสกุล, การวินิจฉัย)

**ข้อปฏิบัติที่ต้องทำ:**

1. ✅ **ฐานกฎหมายในการประมวลผล**
   - โรงพยาบาลมีฐานกฎหมายในการประมวลผลข้อมูล (ปฏิบัติตามสัญญา, หน้าที่ตามกฎหมาย)
   - ใช้เพื่อการรักษาพยาบาล บริหารจัดการ และการเบิกจ่าย

2. ⚠️ **รักษาความมั่นคงปลอดภัย**
   - ตั้งรหัสผ่าน database ที่แข็งแรง
   - เข้าถึงได้เฉพาะบุคลากรที่ได้รับอนุญาต
   - ใช้ VPN หรือ private network เท่านั้น
   - **ห้ามเปิด public internet** โดยเด็ดขาด

3. ⚠️ **จำกัดการเข้าถึง (Access Control)**
   - ตั้งค่า firewall ให้เข้าถึงได้เฉพาะ IP ภายในโรงพยาบาล
   - พิจารณาเพิ่ม authentication (username/password login)
   - จำกัด user permissions ตามความจำเป็น

4. ⚠️ **การเก็บรักษาและลบทิ้ง**
   - เก็บข้อมูลเท่าที่จำเป็น (ตามระเบียบของ NHSO)
   - ลบข้อมูลเมื่อหมดความจำเป็น
   - Backup ต้องเข้ารหัส

5. ⚠️ **ห้ามแชร์หรือเปิดเผย**
   - ห้ามส่งข้อมูลออกนอกโรงพยาบาล
   - ห้ามแชร์ไฟล์ผ่าน cloud storage สาธารณะ
   - ห้าม export ข้อมูลผู้ป่วยไปใช้นอกวัตถุประสงค์

### การใช้งานที่ไม่เหมาะสม ❌

**ห้าม** ใช้โปรแกรมนี้เพื่อ:
- ❌ ขายหรือแชร์ข้อมูลผู้ป่วยให้บุคคลภายนอก
- ❌ ใช้ข้อมูลนอกวัตถุประสงค์ (เช่น การตลาด, วิจัยโดยไม่ได้รับความยินยอม)
- ❌ เปิดเผยข้อมูลส่วนบุคคลโดยไม่ได้รับอนุญาต
- ❌ Deploy บน public cloud โดยไม่มีมาตรการรักษาความปลอดภัย

### Disclaimer (ข้อจำกัดความรับผิด)

```
โปรแกรมนี้พัฒนาเพื่อช่วยโรงพยาบาลในการจัดการข้อมูล e-claim
ผู้พัฒนาไม่รับผิดชอบต่อ:
- การใช้งานที่ไม่ถูกต้องตามกฎหมาย
- ความเสียหายที่เกิดจากการรั่วไหลของข้อมูล
- การละเมิด PDPA หรือกฎหมายอื่นๆ จากการใช้งาน

ผู้ใช้งานต้องรับผิดชอบในการ:
- ตรวจสอบความถูกต้องของข้อมูล
- ปฏิบัติตาม PDPA และกฎหมายที่เกี่ยวข้อง
- รักษาความปลอดภัยของข้อมูลผู้ป่วย
```

### แนะนำสำหรับ Production 🏥

1. **Network Security**
   ```bash
   # ใช้ internal network เท่านั้น
   # ตั้งค่า firewall
   ufw allow from 192.168.1.0/24 to any port 5001
   ```

2. **Authentication** (พิจารณาเพิ่ม)
   - เพิ่ม login system สำหรับ Web UI
   - ใช้ OAuth/LDAP integrate กับระบบโรงพยาบาล
   - Two-factor authentication (2FA)

3. **Audit Logging**
   - บันทึก log ทุกการเข้าถึง
   - Monitor การ download และ export
   - ตั้ง alert สำหรับกิจกรรมผิดปกติ

4. **Data Encryption**
   - เข้ารหัส database (PostgreSQL encryption)
   - เข้ารหัส backups
   - ใช้ SSL/TLS สำหรับ database connection

5. **Regular Updates**
   - อัพเดท security patches
   - ตรวจสอบ dependencies ที่มีช่องโหว่
   - Backup ข้อมูลสม่ำเสมอ

---

## 📚 Documentation

- [Docker Setup Guide](DOCKER.md) - Complete Docker documentation
- [Database Import Guide](database/IMPORT_GUIDE.md) - Import system documentation
- [E-Claim Analysis Report](ECLAIM_ANALYSIS_REPORT.md) - File structure analysis

---

## 👨‍💻 Developer

**Sathit Seethaphon**

If you find this project helpful, consider buying me a coffee! ☕

<a href="https://www.buymeacoffee.com/sathit" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

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

**Made with ❤️ by [aegisx platform](https://github.com/aegisx-platform)**
