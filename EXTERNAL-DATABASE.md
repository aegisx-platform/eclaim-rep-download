# การเชื่อมต่อกับ Database ภายนอก

เมื่อต้องการเชื่อมต่อ Application Container กับ Database ที่อยู่บน Host Machine, LAN หรือ External Server

## วิธีมาตรฐาน (Host Network Mode - แนะนำ)

`docker-compose-deploy-no-db.yml` ใช้ **Host Network Mode** เป็นค่าเริ่มต้น

**ข้อดี:**
- ✅ Container ใช้ network stack ของ host โดยตรง
- ✅ เชื่อมต่อ `localhost` หรือ IP ใดๆ ในเครือข่ายได้เลย
- ✅ ไม่มี network overhead หรือ NAT
- ✅ ไม่ต้องกังวลเรื่อง Docker network isolation

### การใช้งาน

```bash
# 1. Copy example config
cp .env.external-db.example .env

# 2. แก้ไข .env
nano .env

# 3. ตั้งค่า DB_HOST (ใช้ IP หรือ hostname ตรงๆ)
DB_HOST=localhost              # Database บน host (same server)
# หรือ
DB_HOST=192.168.0.218          # Database บน LAN
# หรือ
DB_HOST=10.0.1.100             # Database บนเครือข่ายภายใน
# หรือ
DB_HOST=db.example.com         # Database hostname

# 4. Start container
docker-compose -f docker-compose-deploy-no-db.yml up -d

# 5. Check logs
docker-compose -f docker-compose-deploy-no-db.yml logs -f web

# 6. เข้าใช้งาน
# Web UI: http://localhost:5001
```

## การทำงานของ Host Network Mode

Container ไม่มี network namespace แยก จะใช้ network interface ของ host โดยตรง:

```bash
# เข้า container shell
docker-compose exec web bash

# เช็ค network - จะเหมือนกับ host เลย
ip addr show
# จะเห็น network interfaces เดียวกับ host

# Ping/Connect ทำงานเหมือนอยู่บน host
ping 192.168.0.218
nc -zv 192.168.0.218 3306
```

**หมายเหตุ:** เมื่อใช้ host network mode:
- ไม่สามารถใช้ `ports:` mapping ได้ (ไม่จำเป็นแล้ว)
- Application จะ bind กับ port บน host โดยตรง
- ใช้ `localhost:5001` เข้าถึงได้เลย

## การตรวจสอบการเชื่อมต่อ

### 1. ทดสอบจากภายใน Container

```bash
# เข้า container shell
docker-compose exec web bash

# ทดสอบ ping host
ping -c 2 host.docker.internal

# ทดสอบเชื่อมต่อ database port
nc -zv host.docker.internal 3306      # MySQL
nc -zv host.docker.internal 5432      # PostgreSQL

# ทดสอบด้วย Python
python -c "
from config.database import get_db_config
import pymysql  # หรือ psycopg2
conn = pymysql.connect(**get_db_config())
print('✓ Connected to database successfully')
conn.close()
"
```

### 2. ตรวจสอบ Database Logs (บน Host)

```bash
# MySQL
sudo tail -f /var/log/mysql/error.log

# PostgreSQL
sudo tail -f /var/log/postgresql/postgresql-15-main.log
```

## การตั้งค่า Database บน Host

### MySQL

```bash
# 1. ตรวจสอบ bind-address
sudo nano /etc/mysql/mysql.conf.d/mysqld.cnf

# เปลี่ยนเป็น:
bind-address = 0.0.0.0

# 2. สร้าง database และ user
mysql -u root -p
```

```sql
-- สร้าง database
CREATE DATABASE IF NOT EXISTS eclaim_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- สร้าง user และ grant access จาก Docker network
CREATE USER IF NOT EXISTS 'eclaim'@'%' IDENTIFIED BY 'eclaim_password';
GRANT ALL PRIVILEGES ON eclaim_db.* TO 'eclaim'@'%';
FLUSH PRIVILEGES;

-- ตรวจสอบ
SELECT User, Host FROM mysql.user WHERE User = 'eclaim';
SHOW GRANTS FOR 'eclaim'@'%';
```

```bash
# 3. Restart MySQL
sudo systemctl restart mysql

# 4. ตรวจสอบว่า listen ที่ 0.0.0.0
sudo netstat -tulpn | grep mysql
# ควรเห็น: 0.0.0.0:3306
```

### PostgreSQL

```bash
# 1. แก้ไข postgresql.conf
sudo nano /etc/postgresql/15/main/postgresql.conf

# เปลี่ยนเป็น:
listen_addresses = '*'

# 2. แก้ไข pg_hba.conf
sudo nano /etc/postgresql/15/main/pg_hba.conf

# เพิ่มบรรทัดนี้ (ก่อน local all all):
# TYPE  DATABASE        USER            ADDRESS                 METHOD
host    eclaim_db       eclaim          172.17.0.0/16          md5

# 3. Restart PostgreSQL
sudo systemctl restart postgresql

# 4. ตรวจสอบว่า listen ที่ 0.0.0.0
sudo netstat -tulpn | grep postgres
# ควรเห็น: 0.0.0.0:5432

# 5. สร้าง database และ user
sudo -u postgres psql
```

```sql
-- สร้าง database
CREATE DATABASE eclaim_db;

-- สร้าง user
CREATE USER eclaim WITH PASSWORD 'eclaim_password';

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE eclaim_db TO eclaim;

-- ตรวจสอบ
\l eclaim_db
\du eclaim
```

## Troubleshooting

### ปัญหา: Connection timeout

```bash
# 1. เช็ค firewall
sudo ufw status
sudo ufw allow 3306/tcp  # MySQL
sudo ufw allow 5432/tcp  # PostgreSQL

# 2. เช็คว่า database listen ที่ 0.0.0.0
sudo netstat -tulpn | grep -E "(mysql|postgres)"

# 3. ทดสอบจาก container
docker-compose exec web bash
telnet host.docker.internal 3306
```

### ปัญหา: Access denied

```bash
# ตรวจสอบ user permissions
# MySQL:
mysql -u root -p -e "SELECT User, Host FROM mysql.user WHERE User = 'eclaim';"

# PostgreSQL:
sudo -u postgres psql -c "\du eclaim"
```

### ปัญหา: host.docker.internal not found (Docker เวอร์ชันเก่า)

```bash
# ใช้ bridge gateway IP แทน
docker network inspect bridge | grep Gateway
# แล้วตั้งค่า DB_HOST=172.17.0.1 ใน .env
```

## Security Best Practices

1. **ใช้ Strong Password:**
   ```bash
   # Generate secure password
   openssl rand -base64 32
   ```

2. **จำกัด Network Access:**
   ```bash
   # MySQL - อนุญาตเฉพาะ Docker subnet
   GRANT ALL ON eclaim_db.* TO 'eclaim'@'172.17.%';
   
   # PostgreSQL - ใน pg_hba.conf
   host eclaim_db eclaim 172.17.0.0/16 md5
   ```

3. **ใช้ SSL/TLS (Production):**
   - MySQL: เปิด `require_secure_transport`
   - PostgreSQL: ตั้งค่า `ssl = on`

## Alternative: Host Network Mode

ถ้าต้องการ performance สูงสุดและไม่กังวลเรื่อง network isolation:

```yaml
# docker-compose-deploy-no-db.yml
services:
  web:
    network_mode: "host"
    environment:
      DB_HOST: localhost  # หรือ 127.0.0.1
```

**ข้อดี:**
- ไม่มี network overhead
- ใช้ localhost ได้เลย

**ข้อเสีย:**
- Container ใช้ host's network stack โดยตรง
- Port mapping (`ports:`) ใช้ไม่ได้
- Security isolation น้อยกว่า

