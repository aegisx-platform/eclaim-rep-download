# 🔧 Configuration Guide

## Settings File (config/settings.json)

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

### Settings Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `eclaim_username` | string | - | E-Claim login username |
| `eclaim_password` | string | - | E-Claim login password |
| `download_dir` | string | "downloads" | Directory for downloaded files |
| `auto_import_default` | boolean | false | Auto-import after manual download |
| `schedule_enabled` | boolean | false | Enable/disable scheduler |
| `schedule_times` | array | [] | List of scheduled times |
| `schedule_auto_import` | boolean | false | Auto-import after scheduled download |

### Editing via Web UI

1. Go to **Settings** page
2. Update credentials or schedule
3. Click **Save** button
4. Changes take effect immediately

## Environment Variables

Create `.env` file from `.env.example`:

```bash
cp .env.example .env
nano .env
```

### Required Variables

```bash
# E-Claim Credentials
ECLAIM_USERNAME=your_username_here
ECLAIM_PASSWORD=your_password_here
```

### Database Variables (for Full Stack)

#### PostgreSQL (default)

```bash
DB_TYPE=postgresql
DB_HOST=db
DB_PORT=5432
DB_NAME=eclaim_db
DB_USER=eclaim
DB_PASSWORD=eclaim_password
```

#### MySQL

```bash
DB_TYPE=mysql
DB_HOST=db
DB_PORT=3306
DB_NAME=eclaim_db
DB_USER=eclaim
DB_PASSWORD=eclaim_password
```

#### No Database (Download Only)

```bash
DB_TYPE=none
```

### Optional Variables

```bash
# Timezone
TZ=Asia/Bangkok

# Flask Environment
FLASK_ENV=production  # or 'development'

# pgAdmin (PostgreSQL only)
PGADMIN_DEFAULT_EMAIL=admin@eclaim.local
PGADMIN_DEFAULT_PASSWORD=admin

# Web Server Port
FLASK_PORT=5001
```

### All Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ECLAIM_USERNAME` | - | E-Claim login username |
| `ECLAIM_PASSWORD` | - | E-Claim login password |
| `DB_TYPE` | postgresql | Database type (postgresql/mysql/none) |
| `DB_HOST` | db | Database host |
| `DB_PORT` | 5432 | Database port (5432 for PostgreSQL, 3306 for MySQL) |
| `DB_NAME` | eclaim_db | Database name |
| `DB_USER` | eclaim | Database user |
| `DB_PASSWORD` | eclaim_password | Database password |
| `TZ` | Asia/Bangkok | Timezone |
| `FLASK_ENV` | production | Flask environment (production/development) |
| `FLASK_PORT` | 5001 | Web server port |
| `PGADMIN_DEFAULT_EMAIL` | admin@eclaim.local | pgAdmin email |
| `PGADMIN_DEFAULT_PASSWORD` | admin | pgAdmin password |

## Configuration Priority

Settings are loaded in this order (later overrides earlier):

1. **Default values** (hardcoded in code)
2. **Environment variables** (.env file)
3. **Settings file** (config/settings.json)

**Example:**
```
ECLAIM_USERNAME in .env = "user1"
eclaim_username in settings.json = "user2"
→ Result: "user2" is used
```

## Database Configuration

### PostgreSQL Connection String

```
postgresql://eclaim:eclaim_password@localhost:5432/eclaim_db
```

### MySQL Connection String

```
mysql://eclaim:eclaim_password@localhost:3306/eclaim_db
```

### External Database (not in Docker)

Update `.env`:

```bash
DB_HOST=your-db-server.com
DB_PORT=5432
DB_NAME=eclaim_db
DB_USER=eclaim
DB_PASSWORD=your_secure_password
```

## Security Recommendations

### Production Environment

1. **Change default passwords:**
   ```bash
   DB_PASSWORD=your_strong_password_here
   PGADMIN_DEFAULT_PASSWORD=your_admin_password_here
   ```

2. **Restrict database access:**
   ```bash
   # In docker-compose.yml, remove port mapping
   # ports:
   #   - "5432:5432"  # Comment this out
   ```

3. **Use environment-specific .env:**
   ```bash
   .env.production
   .env.development
   .env.testing
   ```

4. **Never commit .env to git:**
   ```bash
   # Already in .gitignore
   .env
   config/settings.json
   ```

## Backup Configuration

### Backup Settings

```bash
# Backup current settings
cp config/settings.json config/settings.json.backup

# Backup environment
cp .env .env.backup
```

### Restore Settings

```bash
# Restore from backup
cp config/settings.json.backup config/settings.json
cp .env.backup .env

# Restart services
docker-compose restart
```

## Troubleshooting Configuration

### Settings not saved

Check file permissions:
```bash
ls -la config/settings.json
chmod 644 config/settings.json
```

### Environment variables not loaded

```bash
# Check .env file exists
ls -la .env

# Restart containers
docker-compose down
docker-compose up -d
```

### Database connection failed

```bash
# Test database connection
docker-compose exec web python -c "from config.database import get_db_config; print(get_db_config())"

# Check database is running
docker-compose ps db
```

---

**[← Back: Installation](INSTALLATION.md)** | **[Next: Usage Guide →](USAGE.md)**
