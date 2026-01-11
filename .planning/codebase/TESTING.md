# Testing Patterns

**Analysis Date:** 2026-01-11

## Test Framework

**Runner:**
- None configured - No formal test suite exists
- `.gitignore` includes `.pytest_cache/` but pytest not in `requirements.txt`

**Assertion Library:**
- Not applicable (no tests)

**Run Commands:**
```bash
# Lint only (no test suite)
make lint                                    # Run flake8 linter
docker-compose exec web python -m flake8 .  # Direct flake8

# Manual testing via CLI
python eclaim_downloader_http.py            # Test downloader
python eclaim_import.py downloads/file.xls  # Test importer
```

## Test File Organization

**Location:**
- No test files exist
- No `tests/` directory
- Makefile references `tests/` but directory doesn't exist

**Naming:**
- Not established (no tests)

**Structure:**
- Not applicable

## Current Testing Approach

**Manual Testing:**
The project relies on manual testing via CLI tools and Docker Compose.

**Database Connection Test:**
```bash
docker-compose exec web python -c "
from config.database import get_db_config
import psycopg2
conn = psycopg2.connect(**get_db_config())
print('✓ Connected')
"
```

**Downloader Test:**
```bash
docker-compose exec web python eclaim_downloader_http.py
```

**Importer Test:**
```bash
docker-compose exec web python eclaim_import.py downloads/sample.xls
```

**Data Validation:**
```bash
docker-compose exec db psql -U eclaim -d eclaim_db -c \
  "SELECT COUNT(*) FROM claim_rep_opip_nhso_item;"
```

## Linting

**Framework:**
- Flake8 (configured in Makefile)
- Max line length: 120 characters

**Configuration:**
```makefile
lint:
    docker-compose exec web python -m flake8 . \
        --exclude=venv,__pycache__ \
        --max-line-length=120
```

**No Configuration Files:**
- No `.flake8` file
- No `pyproject.toml` lint config
- Uses command-line defaults

## Mocking

**Framework:**
- Not applicable (no tests)

**Patterns:**
- Not established

## Fixtures and Factories

**Test Data:**
- Not applicable (no tests)

**Location:**
- Not applicable

## Coverage

**Requirements:**
- No coverage requirements
- No coverage tool configured

**Configuration:**
- Not applicable

## Test Types

**Unit Tests:**
- Not present
- Would be valuable for: parser, importer, column mapping

**Integration Tests:**
- Not present
- Would be valuable for: database operations, download flow

**E2E Tests:**
- Not present
- Manual testing via CLI serves this purpose

## Common Patterns

**What Would Be Tested (if tests existed):**

**Parser Testing:**
```python
# Example structure for future tests
def test_parse_filename():
    parser = EClaimFileParser('eclaim_10670_IP_25680122_205506156.xls')
    metadata = parser.metadata
    assert metadata['hospital_code'] == '10670'
    assert metadata['file_type'] == 'IP'

def test_parse_thai_date():
    result = EClaimFileParser._parse_thai_date('15/01/2568')
    assert result == '2568-01-15'
```

**Importer Testing:**
```python
# Example structure for future tests
def test_column_mapping():
    # Verify OPIP_COLUMN_MAP maps all expected columns
    required_columns = ['tran_id', 'hn', 'pid', ...]
    for col in required_columns:
        assert col in OPIP_COLUMN_MAP.values()
```

**Database Testing:**
```python
# Example structure for future tests
def test_upsert_duplicate():
    # Test that duplicate (tran_id, file_id) updates rather than fails
    importer = EClaimImporterV2(...)
    importer.import_opip_batch(file_id, df)
    importer.import_opip_batch(file_id, df)  # Should not raise
```

## Testing Gaps

**Critical Untested Areas:**
1. Column mapping (`utils/eclaim/importer_v2.py`) - 49 columns with newline characters
2. Thai date parsing - Buddhist Era conversion
3. Download history deduplication
4. Database UPSERT logic
5. Scheduler job execution
6. SSE log streaming

**Recommended Test Setup:**
1. Add pytest to `requirements.txt`
2. Create `tests/` directory
3. Start with unit tests for `parser.py` and `importer_v2.py`
4. Add fixtures for sample Excel files
5. Configure coverage reporting

---

*Testing analysis: 2026-01-11*
*Update when test patterns change*
