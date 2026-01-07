# E-Claim Excel File Downloader

โปรแกรมสำหรับ download Excel files อัตโนมัติจากระบบ NHSO e-claim validation page

## Features

- ✅ Login อัตโนมัติเข้าระบบ e-claim
- ✅ Download Excel files ทั้งหมดจากหน้า validation
- ✅ เก็บประวัติการ download (ไม่ download ซ้ำ)
- ✅ ใช้ HTTP Client (requests) - เร็วและเบา ไม่ต้องเปิด browser
- ✅ พร้อม run เป็น cron job หรือ scheduled task

## Installation

1. Install Python dependencies:

```bash
pip install -r requirements.txt
```

2. Configure credentials:

Copy `.env.example` to `.env` and update with your credentials:

```bash
cp .env.example .env
```

Edit `.env`:
```
ECLAIM_USERNAME=your_username
ECLAIM_PASSWORD=your_password
DOWNLOAD_DIR=./downloads
```

## Usage

### วิธีที่ 1: HTTP Client Version (แนะนำ - เร็วกว่า)

```bash
python eclaim_downloader_http.py
```

### วิธีที่ 2: Browser Automation Version (ถ้า HTTP Client ไม่ทำงาน)

ต้อง install playwright browsers ก่อน:
```bash
pip install playwright
playwright install chromium
```

จากนั้นรัน:
```bash
python eclaim_downloader.py
```

## Output

### Downloaded Files

ไฟล์ที่ download จะถูกเก็บใน directory ที่กำหนดใน `.env` (default: `./downloads/`)

### Download History

ประวัติการ download จะถูกเก็บใน `download_history.json`:

```json
{
  "last_run": "2026-01-07T14:30:00.123456",
  "downloads": [
    {
      "filename": "rep_eclaim_10670_OP_25690105_20150185.xls",
      "download_date": "2026-01-07T14:30:05.123456",
      "file_path": "./downloads/rep_eclaim_10670_OP_25690105_20150185.xls",
      "file_size": 51200,
      "url": "https://eclaim.nhso.go.th/..."
    }
  ]
}
```

## Automated Scheduling

### Linux/macOS - Cron Job

Edit crontab:
```bash
crontab -e
```

Add line สำหรับ run ทุกวันเวลา 9:00 น.:
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

## Troubleshooting

### ถ้า HTTP Client ไม่ทำงาน

อาจเป็นเพราะ:
- Website มี CSRF token protection
- ต้องการ JavaScript execution
- มี CAPTCHA

แก้ไข: ใช้ `eclaim_downloader.py` (browser version) แทน

### ถ้า download ไม่สำเร็จ

- ตรวจสอบ internet connection
- ตรวจสอบ username/password
- ตรวจสอบว่าระบบ e-claim ทำงานปกติ

## Files Structure

```
eclaim-req-download/
├── .env                          # Configuration (ห้าม commit)
├── .env.example                  # Template
├── .gitignore                    # Git ignore
├── requirements.txt              # Python dependencies
├── eclaim_downloader_http.py     # HTTP Client version (แนะนำ)
├── eclaim_downloader.py          # Browser automation version
├── download_history.json         # Download tracking (auto-generated)
├── downloads/                    # Downloaded files (auto-created)
└── README.md                     # This file
```

## Security Notes

- ⚠️ **ห้าม commit `.env`** file ที่มี credentials
- ⚠️ เก็บ credentials ให้ปลอดภัย
- ⚠️ ตั้งค่า file permissions ให้เหมาะสม

## License

MIT
