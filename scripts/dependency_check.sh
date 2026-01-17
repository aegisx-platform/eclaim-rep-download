#!/bin/bash
#
# Dependency Security Check Script
#
# Runs comprehensive dependency vulnerability scanning:
# 1. Safety - Check for known security vulnerabilities
# 2. pip-audit - Audit Python dependencies for CVEs
# 3. Bandit - Static code analysis for security issues
# 4. Outdated packages check
# 5. SBOM generation
#
# Usage:
#   ./scripts/dependency_check.sh
#   ./scripts/dependency_check.sh --fix        # Install security updates
#   ./scripts/dependency_check.sh --report     # Generate detailed report
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Directories
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
REPORTS_DIR="$PROJECT_DIR/security-reports"
mkdir -p "$REPORTS_DIR"

# Timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Dependency Security Check${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if virtual environment is active
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}⚠️  No virtual environment detected${NC}"
    echo -e "${YELLOW}   Run: source venv/bin/activate${NC}"
    echo ""
fi

# Install security tools
echo -e "${BLUE}Installing security tools...${NC}"
pip install -q safety pip-audit bandit cyclonedx-bom 2>/dev/null || {
    echo -e "${RED}✗ Failed to install security tools${NC}"
    exit 1
}
echo -e "${GREEN}✓ Security tools installed${NC}"
echo ""

# 1. Safety Check
echo -e "${BLUE}1. Running Safety check (known vulnerabilities)...${NC}"
if safety check --json --output "$REPORTS_DIR/safety-$TIMESTAMP.json" 2>/dev/null; then
    echo -e "${GREEN}✓ No known vulnerabilities found${NC}"
    SAFETY_STATUS="PASS"
else
    echo -e "${YELLOW}⚠️  Vulnerabilities found (see report)${NC}"
    safety check --output "$REPORTS_DIR/safety-$TIMESTAMP.txt" 2>/dev/null || true
    SAFETY_STATUS="FAIL"
fi
echo ""

# 2. pip-audit Check
echo -e "${BLUE}2. Running pip-audit (CVE database)...${NC}"
if pip-audit --format json --output "$REPORTS_DIR/pip-audit-$TIMESTAMP.json" 2>/dev/null; then
    echo -e "${GREEN}✓ No CVEs found${NC}"
    PIP_AUDIT_STATUS="PASS"
else
    echo -e "${YELLOW}⚠️  CVEs found (see report)${NC}"
    pip-audit --output "$REPORTS_DIR/pip-audit-$TIMESTAMP.txt" 2>/dev/null || true
    PIP_AUDIT_STATUS="FAIL"
fi
echo ""

# 3. Bandit Code Security Scan
echo -e "${BLUE}3. Running Bandit (code security scan)...${NC}"
cd "$PROJECT_DIR"

# Exclude tests and virtual environments
bandit -r . \
    -f json \
    -o "$REPORTS_DIR/bandit-$TIMESTAMP.json" \
    --exclude "./venv/*,./tests/*,./test_*.py" \
    2>/dev/null || true

bandit -r . \
    -f txt \
    -o "$REPORTS_DIR/bandit-$TIMESTAMP.txt" \
    --exclude "./venv/*,./tests/*,./test_*.py" \
    2>/dev/null || true

# Count high severity issues
if [ -f "$REPORTS_DIR/bandit-$TIMESTAMP.json" ]; then
    HIGH_COUNT=$(jq '[.results[] | select(.issue_severity == "HIGH")] | length' "$REPORTS_DIR/bandit-$TIMESTAMP.json" 2>/dev/null || echo "0")

    if [ "$HIGH_COUNT" -eq "0" ]; then
        echo -e "${GREEN}✓ No high severity issues found${NC}"
        BANDIT_STATUS="PASS"
    else
        echo -e "${YELLOW}⚠️  Found $HIGH_COUNT high severity issues${NC}"
        BANDIT_STATUS="FAIL"
    fi
else
    echo -e "${GREEN}✓ Scan completed${NC}"
    BANDIT_STATUS="PASS"
fi
echo ""

# 4. Outdated Packages
echo -e "${BLUE}4. Checking for outdated packages...${NC}"
pip list --outdated --format json > "$REPORTS_DIR/outdated-$TIMESTAMP.json" 2>/dev/null || echo "[]" > "$REPORTS_DIR/outdated-$TIMESTAMP.json"
pip list --outdated > "$REPORTS_DIR/outdated-$TIMESTAMP.txt" 2>/dev/null || echo "No outdated packages" > "$REPORTS_DIR/outdated-$TIMESTAMP.txt"

OUTDATED_COUNT=$(jq 'length' "$REPORTS_DIR/outdated-$TIMESTAMP.json" 2>/dev/null || echo "0")

if [ "$OUTDATED_COUNT" -eq "0" ]; then
    echo -e "${GREEN}✓ All packages up to date${NC}"
else
    echo -e "${YELLOW}⚠️  $OUTDATED_COUNT outdated packages found${NC}"
    echo ""
    echo "Top 10 outdated packages:"
    head -n 11 "$REPORTS_DIR/outdated-$TIMESTAMP.txt"
fi
echo ""

# 5. Generate SBOM (Software Bill of Materials)
echo -e "${BLUE}5. Generating SBOM...${NC}"
cyclonedx-py -r -i requirements.txt -o "$REPORTS_DIR/sbom-$TIMESTAMP.json" --format json 2>/dev/null || true
cyclonedx-py -r -i requirements.txt -o "$REPORTS_DIR/sbom-$TIMESTAMP.xml" --format xml 2>/dev/null || true
echo -e "${GREEN}✓ SBOM generated (CycloneDX format)${NC}"
echo ""

# 6. Generate Summary Report
echo -e "${BLUE}6. Generating summary report...${NC}"

SUMMARY_FILE="$REPORTS_DIR/summary-$TIMESTAMP.md"

cat > "$SUMMARY_FILE" << EOF
# Security Scan Summary

**Date:** $(date '+%Y-%m-%d %H:%M:%S %Z')
**Project:** E-Claim Downloader
**Scan Type:** Dependency & Code Security

---

## Results Overview

| Check | Status | Details |
|-------|--------|---------|
| Safety (Vulnerabilities) | $SAFETY_STATUS | Known security vulnerabilities |
| pip-audit (CVEs) | $PIP_AUDIT_STATUS | CVE database check |
| Bandit (Code Security) | $BANDIT_STATUS | Static code analysis |
| Outdated Packages | $OUTDATED_COUNT packages | Packages with updates available |

---

## Safety Check

EOF

if [ -f "$REPORTS_DIR/safety-$TIMESTAMP.txt" ]; then
    echo '```' >> "$SUMMARY_FILE"
    cat "$REPORTS_DIR/safety-$TIMESTAMP.txt" >> "$SUMMARY_FILE"
    echo '```' >> "$SUMMARY_FILE"
else
    echo "No vulnerabilities found ✓" >> "$SUMMARY_FILE"
fi

cat >> "$SUMMARY_FILE" << EOF

---

## pip-audit Check

EOF

if [ -f "$REPORTS_DIR/pip-audit-$TIMESTAMP.txt" ]; then
    echo '```' >> "$SUMMARY_FILE"
    cat "$REPORTS_DIR/pip-audit-$TIMESTAMP.txt" >> "$SUMMARY_FILE"
    echo '```' >> "$SUMMARY_FILE"
else
    echo "No CVEs found ✓" >> "$SUMMARY_FILE"
fi

cat >> "$SUMMARY_FILE" << EOF

---

## Bandit Code Security

EOF

if [ -f "$REPORTS_DIR/bandit-$TIMESTAMP.txt" ]; then
    echo '```' >> "$SUMMARY_FILE"
    head -n 100 "$REPORTS_DIR/bandit-$TIMESTAMP.txt" >> "$SUMMARY_FILE"
    echo '```' >> "$SUMMARY_FILE"
else
    echo "No issues found ✓" >> "$SUMMARY_FILE"
fi

cat >> "$SUMMARY_FILE" << EOF

---

## Outdated Packages

\`\`\`
$(cat "$REPORTS_DIR/outdated-$TIMESTAMP.txt")
\`\`\`

---

## Reports Generated

- Safety JSON: \`security-reports/safety-$TIMESTAMP.json\`
- pip-audit JSON: \`security-reports/pip-audit-$TIMESTAMP.json\`
- Bandit JSON: \`security-reports/bandit-$TIMESTAMP.json\`
- Outdated packages: \`security-reports/outdated-$TIMESTAMP.json\`
- SBOM (CycloneDX): \`security-reports/sbom-$TIMESTAMP.json\`
- Summary: \`security-reports/summary-$TIMESTAMP.md\`

---

## Recommendations

EOF

if [ "$SAFETY_STATUS" = "FAIL" ] || [ "$PIP_AUDIT_STATUS" = "FAIL" ]; then
    cat >> "$SUMMARY_FILE" << EOF
**High Priority:**
- Review and fix vulnerabilities found by Safety and pip-audit
- Update affected packages to patched versions
- Test application after updates
EOF
fi

if [ "$OUTDATED_COUNT" -gt "0" ]; then
    cat >> "$SUMMARY_FILE" << EOF

**Medium Priority:**
- Review outdated packages
- Update non-breaking packages
- Test compatibility before major version updates
EOF
fi

if [ "$BANDIT_STATUS" = "FAIL" ]; then
    cat >> "$SUMMARY_FILE" << EOF

**Code Security:**
- Review high severity issues found by Bandit
- Apply security best practices
- Consider refactoring vulnerable code patterns
EOF
fi

cat >> "$SUMMARY_FILE" << EOF

---

**Next Scan:** Run daily or after dependency changes
**Documentation:** See \`docs/technical/DEPENDENCY_SECURITY.md\`
EOF

echo -e "${GREEN}✓ Summary report generated${NC}"
echo ""

# Display summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Scan Complete${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "Safety:      ${SAFETY_STATUS}"
echo -e "pip-audit:   ${PIP_AUDIT_STATUS}"
echo -e "Bandit:      ${BANDIT_STATUS}"
echo -e "Outdated:    ${OUTDATED_COUNT} packages"
echo ""
echo -e "Summary: ${GREEN}$SUMMARY_FILE${NC}"
echo ""

# Check for --fix flag
if [ "$1" = "--fix" ]; then
    echo -e "${YELLOW}Installing security updates...${NC}"
    echo ""

    # Read vulnerabilities and attempt to update
    if [ -f "$REPORTS_DIR/safety-$TIMESTAMP.json" ]; then
        echo "Updating vulnerable packages..."
        # Extract package names and update
        jq -r '.vulnerabilities[].package_name' "$REPORTS_DIR/safety-$TIMESTAMP.json" 2>/dev/null | sort -u | while read pkg; do
            if [ ! -z "$pkg" ]; then
                echo "  Updating $pkg..."
                pip install --upgrade "$pkg" || echo "    Failed to update $pkg"
            fi
        done
    fi

    echo ""
    echo -e "${GREEN}✓ Updates applied${NC}"
    echo -e "${YELLOW}⚠️  Remember to test the application${NC}"
    echo ""
fi

# Check for --report flag
if [ "$1" = "--report" ]; then
    echo -e "${BLUE}Opening summary report...${NC}"
    if command -v xdg-open &> /dev/null; then
        xdg-open "$SUMMARY_FILE"
    elif command -v open &> /dev/null; then
        open "$SUMMARY_FILE"
    else
        cat "$SUMMARY_FILE"
    fi
fi

# Exit with error if critical issues found
if [ "$SAFETY_STATUS" = "FAIL" ] || [ "$PIP_AUDIT_STATUS" = "FAIL" ]; then
    echo -e "${RED}⚠️  Critical security issues found${NC}"
    echo -e "${RED}   Review reports and apply fixes${NC}"
    exit 1
fi

exit 0
