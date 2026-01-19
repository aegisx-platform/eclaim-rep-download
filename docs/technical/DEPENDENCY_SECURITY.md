# Dependency Security Guide

> Automated vulnerability scanning and dependency management

**Security Level:** 🛡️ Enhanced Security (Phase 2)
**Protection:** CVE detection, outdated packages, code vulnerabilities, supply chain attacks
**Date:** 2026-01-17

---

## Why Dependency Security?

Dependencies are a major attack vector in modern applications:

**Risks without scanning:**
- 🔴 **Known Vulnerabilities:** Using packages with published CVEs
- 🔴 **Supply Chain Attacks:** Compromised packages from PyPI
- 🔴 **Outdated Dependencies:** Missing critical security patches
- 🔴 **Code Vulnerabilities:** Insecure patterns in your code
- 🔴 **License Violations:** Using incompatible licenses

**Real-world examples:**
- Log4Shell (CVE-2021-44228) - Critical RCE vulnerability
- Django SQL Injection (CVE-2022-28346)
- Flask CORS Bypass (CVE-2023-30861)
- Pillow Buffer Overflow (CVE-2023-44271)

---

## Quick Start

### Manual Scanning (Local Development)

```bash
# Run full security scan
./scripts/dependency_check.sh

# Run scan and auto-fix vulnerabilities
./scripts/dependency_check.sh --fix

# Run scan and open report
./scripts/dependency_check.sh --report
```

**Expected output:**
- Safety check: Known vulnerabilities
- pip-audit: CVE database check
- Bandit: Code security scan
- Outdated packages: Update recommendations
- SBOM generation: Software inventory
- Summary report: Comprehensive overview

### Automated Scanning (CI/CD)

GitHub Actions runs automatically:
- **Push to main/develop:** Scans on every push
- **Pull requests:** Scans before merge
- **Daily schedule:** 2 AM Bangkok time (7 PM UTC)
- **Manual trigger:** via GitHub UI

---

## Security Tools

### 1. Safety - Known Vulnerabilities

**What it does:** Checks Python packages against Safety DB (180,000+ vulnerabilities)

**Run manually:**
```bash
pip install safety
safety check
safety check --json --output safety-report.json
```

**Features:**
- PyUp vulnerability database
- CVE mappings
- Severity ratings (LOW, MEDIUM, HIGH, CRITICAL)
- Fix recommendations

---

### 2. pip-audit - CVE Database

**What it does:** Audits Python packages against the OSV (Open Source Vulnerabilities) database

**Run manually:**
```bash
pip install pip-audit
pip-audit
pip-audit --format json --output pip-audit-report.json
```

**Features:**
- OSV database (Google-maintained)
- GitHub Security Advisories
- PyPI Advisories
- Auto-fix suggestions

---

### 3. Bandit - Code Security Scanner

**What it does:** Static code analysis to find common security issues

**Run manually:**
```bash
pip install bandit
bandit -r .
bandit -r . -f json -o bandit-report.json
```

**What it detects:**
- Hardcoded passwords
- SQL injection patterns
- Command injection risks
- Insecure temp files
- Weak cryptography
- Debug mode in production
- Assert statements
- Pickle usage

**Severity levels:**
- LOW: Minor security concerns
- MEDIUM: Moderate security issues
- HIGH: Critical security vulnerabilities

---

### 4. SBOM Generation (Software Bill of Materials)

**What it does:** Creates a complete inventory of all dependencies

**Formats:**
- CycloneDX (JSON/XML) - Industry standard for security
- SPDX (Software Package Data Exchange)

**Use cases:**
- Compliance (NTIA, Executive Order 14028)
- Supply chain security
- License compliance
- Vulnerability tracking

**Generated files:**
```
security-reports/
├── sbom-20260117_143052.json    # CycloneDX JSON
├── sbom-20260117_143052.xml     # CycloneDX XML
└── installed-packages.txt        # Simple pip freeze
```

---

### 5. Docker Image Scanning (Trivy)

**What it does:** Scans Docker images for OS and library vulnerabilities

**Run manually:**
```bash
# Install Trivy
brew install aquasecurity/trivy/trivy  # macOS
# OR
apt-get install trivy  # Ubuntu

# Scan image
docker build -t eclaim-app:test .
trivy image eclaim-app:test
```

**What it scans:**
- OS packages (apt, apk, yum)
- Python packages
- Dockerfile misconfigurations
- Secrets in layers
- Kubernetes manifests

---

### 6. Secret Scanning (Gitleaks)

**What it does:** Scans git history for leaked credentials

**Run manually:**
```bash
# Install Gitleaks
brew install gitleaks  # macOS

# Scan repository
gitleaks detect --source . --verbose
```

**What it detects:**
- API keys
- AWS credentials
- Database passwords
- Private keys
- OAuth tokens
- GitHub tokens

---

## CI/CD Integration

### GitHub Actions Workflow

Automatic scanning on:
- Push to main/develop
- Pull requests
- Daily at 2 AM Bangkok time
- Manual trigger

**Workflow file:** `.github/workflows/security-scan.yml`

**Jobs:**
1. `dependency-scan` - Safety + pip-audit + outdated packages
2. `code-security-scan` - Bandit static analysis
3. `sbom-generation` - Generate Software Bill of Materials
4. `docker-security-scan` - Trivy Docker image scan
5. `secret-scan` - Gitleaks secret scanning
6. `security-summary` - Generate summary report

**Artifacts generated:**
- `security-reports/` - JSON and text reports
- `bandit-report/` - Code security findings
- `sbom/` - Software Bill of Materials
- `security-summary/` - Markdown summary

**View reports:**
1. Go to GitHub Actions
2. Click on latest "Security Scan" workflow
3. Download artifacts

---

## Dependabot Integration

### Enable Dependabot

**Create:** `.github/dependabot.yml`

```yaml
version: 2
updates:
  # Python dependencies
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "02:00"
      timezone: "Asia/Bangkok"
    open-pull-requests-limit: 10
    labels:
      - "dependencies"
      - "security"
    commit-message:
      prefix: "chore(deps)"
      include: "scope"
    reviewers:
      - "your-team"
    assignees:
      - "security-team"
    # Auto-merge minor updates
    allow:
      - dependency-type: "direct"
        update-type: "version-update:semver-patch"
    # Ignore specific packages
    ignore:
      - dependency-name: "package-to-ignore"
        versions: ["1.x"]

  # Docker dependencies
  - package-ecosystem: "docker"
    directory: "/"
    schedule:
      interval: "weekly"

  # GitHub Actions
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
```

**Features:**
- Automatic pull requests for updates
- Security vulnerability alerts
- Auto-merge for patch updates
- Grouped updates
- Custom labels and reviewers

---

## Usage Examples

### Local Development Workflow

```bash
# 1. Before starting work - check current state
./scripts/dependency_check.sh

# 2. Install/update dependencies
pip install -r requirements.txt

# 3. After adding new dependencies
echo "new-package==1.0.0" >> requirements.txt
pip install new-package==1.0.0

# 4. Check for vulnerabilities
./scripts/dependency_check.sh

# 5. If vulnerabilities found - apply fixes
./scripts/dependency_check.sh --fix

# 6. Test application
pytest

# 7. Commit changes
git add requirements.txt
git commit -m "feat: add new-package for feature X"
```

### Handling Vulnerabilities

**Vulnerability Response Workflow:**

1. **Identify the issue** - Run dependency_check.sh to detect vulnerabilities
2. **Check changelog** - Review package changelog for breaking changes
3. **Test update** - Create test branch and update package version
4. **Run tests** - Verify application functionality
5. **Verify fix** - Run dependency_check.sh again
6. **Deploy** - Commit, create PR, merge after review

**Priority levels:**
| Severity | Response Time | Action |
|----------|---------------|--------|
| CRITICAL | < 24 hours | Hotfix, emergency deployment |
| HIGH | < 1 week | Scheduled patch release |
| MEDIUM | < 1 month | Include in next release |
| LOW | Next major version | Plan for refactor |

---

## Automated Fix Workflow

```bash
# Run scan with auto-fix
./scripts/dependency_check.sh --fix
```

**What happens:**
1. Scans for vulnerabilities
2. Extracts vulnerable package names
3. Upgrades packages to patched versions
4. Generates updated pip freeze output
5. Prompts to update requirements.txt

**Caution:**
- May introduce breaking changes
- Always test after auto-fix
- Review upgrade paths for major versions
- Check changelog for compatibility

---

## Best Practices

### 1. Pin Dependencies

**Good:**
```txt
Flask==3.0.0
psycopg2-binary==2.9.9
pydantic==2.5.3
```

**Bad:**
```txt
Flask>=2.0.0
psycopg2-binary
pydantic~=2.0
```

**Why:** Reproducible builds, prevent surprise breakage

### 2. Use Version Ranges for Security

**Example:**
```txt
# Allow patch updates only
Flask>=3.0.0,<3.1.0

# Allow minor updates
psycopg2-binary>=2.9.0,<3.0.0
```

### 3. Separate Dev Dependencies

```txt
# requirements.txt (production)
Flask==3.0.0
psycopg2-binary==2.9.9

# requirements-dev.txt (development)
-r requirements.txt
pytest==7.4.0
bandit==1.7.5
safety==2.3.5
```

### 4. Regular Scans

- Daily automated scans (GitHub Actions)
- Weekly manual review
- Before each deployment
- After dependency changes

### 5. SBOM Management

- Generate SBOM for each release
- Store in version control or artifact repository
- Share with security team
- Use for compliance audits

### 6. Dependency Review

Before adding new dependency, check:
- ✅ Last updated within 6 months
- ✅ Active maintenance (commits, issues)
- ✅ No known critical vulnerabilities
- ✅ Compatible license (MIT, BSD, Apache 2.0)
- ✅ Reasonable size (avoid bloat)
- ✅ Good documentation

---

## Troubleshooting

### Issue: "No vulnerabilities found" but package is known vulnerable

**Cause:** Safety database not up to date

**Solution:**
```bash
# Update Safety database
safety check --update

# Use pip-audit as second opinion
pip-audit
```

### Issue: False positives in Bandit

**Cause:** Bandit doesn't understand context

**Solution:** Add `# nosec` comment with justification
```python
# Safe: input is validated by Pydantic schema before use
validated_input = schema.validate(user_input)  # nosec B603
```

### Issue: CI/CD workflow fails with "jq: command not found"

**Cause:** jq not installed in CI environment

**Solution:** Add to workflow
```yaml
- name: Install jq
  run: sudo apt-get install -y jq
```

### Issue: Too many Dependabot PRs

**Cause:** Default limit is 5 per week

**Solution:** Adjust in `.github/dependabot.yml`
```yaml
open-pull-requests-limit: 10  # Increase limit
```

Or group updates:
```yaml
groups:
  dependencies:
    patterns:
      - "*"
```

---

## Reports Reference

### Safety Report (JSON)

Contains:
- `report_meta` - Scan metadata
- `vulnerabilities` - Array of vulnerability objects
  - `package_name` - Affected package
  - `vulnerable_spec` - Vulnerable version range
  - `advisory` - Vulnerability description
  - `vulnerability_id` - CVE identifier
  - `severity` - CVSS score and level
  - `fixed_versions` - Patched versions

### Bandit Report (JSON)

Contains:
- `metrics` - Total lines scanned, total issues
- `results` - Array of issue objects
  - `filename` - File with issue
  - `line_number` - Line number
  - `issue_severity` - HIGH, MEDIUM, LOW
  - `issue_confidence` - HIGH, MEDIUM, LOW
  - `issue_text` - Description
  - `test_id` - Bandit test identifier

---

## Integration with Application

### Security Status Dashboard

Add security status to web UI:

**app.py:**
```python
from pathlib import Path

@app.route('/security-status')
@login_required
def security_status():
    """Display security scan results."""

    report_dir = Path('security-reports')
    if not report_dir.exists():
        return render_template('security_status.html', no_reports=True)

    # Find latest summary
    summaries = list(report_dir.glob('summary-*.md'))
    if not summaries:
        return render_template('security_status.html', no_reports=True)

    latest_summary = max(summaries, key=lambda p: p.stat().st_mtime)

    with open(latest_summary) as f:
        content = f.read()

    return render_template('security_status.html', report_content=content)
```

### Automatic Alerts

Create alert system for critical vulnerabilities:

**utils/security_alerts.py:**
```python
import json
from pathlib import Path
from datetime import datetime

def check_and_alert():
    """Check security reports and send alerts if critical issues found."""

    report_dir = Path('security-reports')
    safety_reports = list(report_dir.glob('safety-*.json'))

    if not safety_reports:
        return

    latest_report = max(safety_reports, key=lambda p: p.stat().st_mtime)

    with open(latest_report) as f:
        report = json.load(f)

    critical_vulns = [
        v for v in report.get('vulnerabilities', [])
        if v.get('severity', {}).get('base_severity') == 'CRITICAL'
    ]

    if critical_vulns:
        send_email_alert(
            title="Critical Security Vulnerabilities Detected",
            count=len(critical_vulns),
            packages=[v['package_name'] for v in critical_vulns]
        )
```

---

## Resources

- **Safety:** https://pyup.io/safety/
- **pip-audit:** https://github.com/pypa/pip-audit
- **Bandit:** https://bandit.readthedocs.io/
- **CycloneDX:** https://cyclonedx.org/
- **Trivy:** https://aquasecurity.github.io/trivy/
- **Gitleaks:** https://github.com/gitleaks/gitleaks
- **OWASP Dependency Check:** https://owasp.org/www-project-dependency-check/
- **NTIA SBOM:** https://www.ntia.gov/SBOM

---

**Last Updated:** 2026-01-17
**Maintainer:** Security Team

**Next:** [Phase 2 Complete](PHASE2_COMPLETE.md) | [Phase 3 Planning](../roadmap/PHASE3_PLAN.md)
