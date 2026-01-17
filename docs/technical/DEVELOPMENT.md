# 🔨 Development Guide

## Project Structure

```
eclaim-req-download/
├── app.py                          # Flask web application
├── eclaim_downloader_http.py       # HTTP Client downloader
├── bulk_downloader.py              # Bulk download orchestrator
├── download_with_import.py         # Download wrapper with import
├── eclaim_import.py                # CLI import tool
├── Dockerfile                      # Docker image definition
├── docker-compose.yml              # Full stack (PostgreSQL)
├── docker-compose-mysql.yml        # Full stack (MySQL)
├── docker-compose-no-db.yml        # Download-only
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
│   ├── schema-postgresql-merged.sql  # PostgreSQL schema V2
│   ├── schema-mysql-merged.sql       # MySQL schema V2
│   └── IMPORT_GUIDE.md               # Import documentation
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
│       ├── importer.py             # Database importer (old)
│       └── importer_v2.py          # Database importer
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
├── docs/                           # Documentation
│   ├── FEATURES.md
│   ├── INSTALLATION.md
│   ├── CONFIGURATION.md
│   ├── USAGE.md
│   ├── DATABASE.md
│   ├── LEGAL.md
│   ├── TROUBLESHOOTING.md
│   └── DEVELOPMENT.md
│
├── downloads/                      # Downloaded Excel files
├── logs/                           # Application logs
└── backups/                        # Database backups
```

## Development Setup

### Prerequisites

- Python 3.12+
- Docker & Docker Compose
- Git
- PostgreSQL or MySQL (optional)

### Local Development

```bash
# Clone repository
git clone https://github.com/aegisx-platform/eclaim-req-download.git
cd eclaim-req-download

# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Run development server
FLASK_ENV=development python app.py
```

### Docker Development

```bash
# Build and run with hot reload
docker-compose up --build

# Logs
docker-compose logs -f

# Shell access
docker-compose exec web bash
```

## Technology Stack

### Backend

- **Python 3.12** - Core language
- **Flask 3.0** - Web framework
- **APScheduler 3.10** - Task scheduling
- **Requests** - HTTP client
- **pandas** - Excel parsing
- **xlrd** - XLS file reading
- **psycopg2** - PostgreSQL driver
- **pymysql** - MySQL driver

### Frontend

- **Tailwind CSS** - UI framework
- **Vanilla JavaScript** - No frameworks
- **Server-Sent Events (SSE)** - Real-time updates
- **Fetch API** - AJAX requests

### Infrastructure

- **Docker** - Containerization
- **PostgreSQL 15** / **MySQL 8.0** - Databases
- **pgAdmin** / **phpMyAdmin** - Database management

## Code Style

### Python

Follow PEP 8 style guide:

```python
# Good
def import_claim_data(file_path: str, db_config: Dict) -> bool:
    """Import claim data from Excel file."""
    pass

# Use type hints
from typing import Dict, List, Optional

# Docstrings for all public functions
def process_data(data: List[Dict]) -> List[Dict]:
    """
    Process claim data.

    Args:
        data: List of claim records

    Returns:
        Processed claim records
    """
    pass
```

### JavaScript

```javascript
// Use async/await
async function fetchData() {
    try {
        const response = await fetch('/api/data');
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error:', error);
    }
}

// Use const/let, not var
const API_URL = '/api/schedule';
let isLoading = false;
```

## Testing

### Manual Testing

```bash
# Test downloader
python eclaim_downloader_http.py

# Test importer
python eclaim_import.py downloads/test_file.xls

# Test API endpoints
curl http://localhost:5001/api/schedule
curl http://localhost:5001/api/stats
```

### Database Testing

```bash
# Test PostgreSQL connection
docker-compose exec db psql -U eclaim -d eclaim_db

# Test import
docker-compose exec web python eclaim_import.py downloads/sample.xls

# Verify data
docker-compose exec db psql -U eclaim -d eclaim_db -c \
  "SELECT COUNT(*) FROM claim_rep_opip_nhso_item;"
```

## Contributing

### Workflow

1. **Fork** the repository
2. **Create feature branch** (`git checkout -b feature/AmazingFeature`)
3. **Make changes** with clear commits
4. **Test thoroughly** (manual + database)
5. **Update documentation** if needed
6. **Push** to your branch (`git push origin feature/AmazingFeature`)
7. **Open Pull Request**

### Commit Messages

```bash
# Good commit messages
git commit -m "Add bulk download feature with progress tracking"
git commit -m "Fix PostgreSQL schema syntax for triggers"
git commit -m "Update README with database schema documentation"

# Include emoji (optional)
git commit -m "✨ Add scheduler status display on dashboard"
git commit -m "🐛 Fix import error with empty date fields"
git commit -m "📚 Update database documentation"
```

### Pull Request Template

```markdown
## Description
Brief description of changes

## Changes Made
- Added feature X
- Fixed bug Y
- Updated documentation Z

## Testing
- [ ] Manual testing completed
- [ ] Docker build successful
- [ ] Documentation updated

## Screenshots (if applicable)
```

## Adding New Features

### Adding New Import Type

1. **Update schema:**
   ```sql
   -- database/schema-postgresql-merged.sql
   CREATE TABLE claim_rep_new_type_item (...);
   ```

2. **Add column mapping:**
   ```python
   # utils/eclaim/importer_v2.py
   NEW_TYPE_COLUMN_MAP = {
       'Excel Column': 'db_column',
       # ...
   }
   ```

3. **Add import method:**
   ```python
   def import_new_type_batch(self, file_id, df):
       # Implementation
       pass
   ```

### Adding New API Endpoint

```python
# app.py
@app.route('/api/new-endpoint', methods=['GET', 'POST'])
def new_endpoint():
    """API endpoint description."""
    try:
        # Implementation
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

### Adding New Scheduled Task

```python
# utils/scheduler.py
def new_scheduled_task():
    """Task description."""
    # Implementation
    pass

# Register in scheduler
scheduler.add_job(
    func=new_scheduled_task,
    trigger='cron',
    hour=9,
    minute=0,
    id='new_task'
)
```

## Debugging

### Enable Debug Mode

```bash
# .env
FLASK_ENV=development
LOG_LEVEL=DEBUG

# Restart
docker-compose restart web
```

### Debug Logs

```python
# Add logging to your code
import logging
logger = logging.getLogger(__name__)

logger.debug('Debug message')
logger.info('Info message')
logger.warning('Warning message')
logger.error('Error message')
logger.exception('Exception with traceback')
```

### Interactive Debugging

```python
# Add breakpoint
import pdb; pdb.set_trace()

# Or use iPython debugger
import ipdb; ipdb.set_trace()
```

## Release Process

### Version Numbering

Follow Semantic Versioning (SemVer):
- **MAJOR** version: Breaking changes
- **MINOR** version: New features (backward compatible)
- **PATCH** version: Bug fixes

### Creating a Release

```bash
# 1. Update version
# Edit: README.md, __init__.py, etc.

# 2. Update CHANGELOG
echo "## v2.0.0 ($(date +%Y-%m-%d))\n- Feature A\n- Bug fix B" >> CHANGELOG.md

# 3. Commit
git add .
git commit -m "Release v2.0.0"

# 4. Tag
git tag -a v2.0.0 -m "Release v2.0.0"

# 5. Push
git push origin main
git push origin v2.0.0
```

### GitHub Release

1. Go to **Releases** > **Create new release**
2. Select tag: `v2.0.0`
3. Release title: `v2.0.0 - Feature Name`
4. Description: Copy from CHANGELOG
5. Attach binaries (if any)
6. Publish release

## Dependencies

### Adding New Dependencies

```bash
# Install package
pip install package-name

# Update requirements
pip freeze > requirements.txt

# Or manually add to requirements.txt
echo "package-name==1.0.0" >> requirements.txt

# Rebuild Docker
docker-compose build --no-cache
```

### Dependency Management

```bash
# List outdated packages
pip list --outdated

# Upgrade package
pip install --upgrade package-name

# Security audit
pip-audit
```

## Performance Optimization

### Database Optimization

```sql
-- Add indexes for frequently queried columns
CREATE INDEX idx_dateadm ON claim_rep_opip_nhso_item(dateadm);

-- Analyze table statistics
ANALYZE claim_rep_opip_nhso_item;

-- Vacuum (PostgreSQL)
VACUUM ANALYZE claim_rep_opip_nhso_item;
```

### Code Optimization

```python
# Use batch operations
# Bad:
for record in records:
    db.insert(record)

# Good:
db.bulk_insert(records)

# Use generators for large datasets
def read_large_file(file_path):
    for chunk in pd.read_excel(file_path, chunksize=1000):
        yield chunk
```

## License

MIT License - see [LICENSE](../LICENSE) file for details

---

**[← Back: Troubleshooting](TROUBLESHOOTING.md)** | **[Back to Main README](../README.md)**
