#!/bin/bash
# Test HTTPS Configuration
# Verifies that HTTPS setup is correct

set -e

echo "=================================="
echo "HTTPS CONFIGURATION TEST"
echo "=================================="
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass=0
fail=0
warn=0

check_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((pass++))
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    ((fail++))
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((warn++))
}

echo "📋 Checking configuration files..."
echo ""

# Check nginx.conf
if [ -f "nginx/nginx.conf" ]; then
    check_pass "nginx.conf exists"

    # Check SSL configuration
    if grep -q "ssl_protocols TLSv1.2 TLSv1.3" nginx/nginx.conf; then
        check_pass "Modern SSL protocols configured (TLSv1.2, TLSv1.3)"
    else
        check_fail "SSL protocols not configured properly"
    fi

    # Check HSTS
    if grep -q "Strict-Transport-Security" nginx/nginx.conf; then
        check_pass "HSTS (HTTP Strict Transport Security) enabled"
    else
        check_warn "HSTS not configured (recommended for production)"
    fi

    # Check security headers
    if grep -q "X-Frame-Options" nginx/nginx.conf; then
        check_pass "Security headers configured"
    else
        check_warn "Security headers missing"
    fi

    # Check rate limiting
    if grep -q "limit_req_zone" nginx/nginx.conf; then
        check_pass "Rate limiting configured"
    else
        check_warn "Rate limiting not configured"
    fi
else
    check_fail "nginx.conf NOT found"
fi

echo ""

# Check docker-compose-https.yml
if [ -f "docker-compose-https.yml" ]; then
    check_pass "docker-compose-https.yml exists"

    # Check nginx service
    if grep -q "nginx:" docker-compose-https.yml; then
        check_pass "nginx service defined"
    else
        check_fail "nginx service NOT defined"
    fi

    # Check HTTPS environment variables
    if grep -q "WTF_CSRF_SSL_STRICT.*true" docker-compose-https.yml; then
        check_pass "CSRF SSL strict mode enabled"
    else
        check_warn "CSRF SSL strict mode not set (check environment)"
    fi

    if grep -q "SESSION_COOKIE_SECURE.*true" docker-compose-https.yml; then
        check_pass "Secure session cookies enabled"
    else
        check_warn "Secure session cookies not set"
    fi
else
    check_fail "docker-compose-https.yml NOT found"
fi

echo ""

# Check SSL scripts
if [ -f "nginx/generate-ssl-dev.sh" ]; then
    check_pass "SSL generation script (dev) exists"
    if [ -x "nginx/generate-ssl-dev.sh" ]; then
        check_pass "SSL generation script is executable"
    else
        check_warn "SSL generation script not executable (run: chmod +x nginx/generate-ssl-dev.sh)"
    fi
else
    check_fail "SSL generation script (dev) NOT found"
fi

if [ -f "nginx/generate-ssl-prod.sh" ]; then
    check_pass "SSL generation script (prod) exists"
    if [ -x "nginx/generate-ssl-prod.sh" ]; then
        check_pass "SSL generation script is executable"
    else
        check_warn "SSL generation script not executable (run: chmod +x nginx/generate-ssl-prod.sh)"
    fi
else
    check_fail "SSL generation script (prod) NOT found"
fi

if [ -f "nginx/renew-ssl.sh" ]; then
    check_pass "SSL renewal script exists"
    if [ -x "nginx/renew-ssl.sh" ]; then
        check_pass "SSL renewal script is executable"
    else
        check_warn "SSL renewal script not executable (run: chmod +x nginx/renew-ssl.sh)"
    fi
else
    check_fail "SSL renewal script NOT found"
fi

echo ""

# Check SSL certificates
if [ -d "nginx/ssl" ]; then
    if [ -f "nginx/ssl/cert.pem" ] && [ -f "nginx/ssl/key.pem" ]; then
        check_pass "SSL certificates exist"

        # Check certificate validity
        if command -v openssl &> /dev/null; then
            EXPIRY_DATE=$(openssl x509 -in nginx/ssl/cert.pem -noout -enddate 2>/dev/null | cut -d= -f2)
            if [ $? -eq 0 ]; then
                EXPIRY_EPOCH=$(date -d "$EXPIRY_DATE" +%s 2>/dev/null || date -j -f "%b %d %H:%M:%S %Y %Z" "$EXPIRY_DATE" +%s 2>/dev/null)
                NOW_EPOCH=$(date +%s)
                DAYS_LEFT=$(( ($EXPIRY_EPOCH - $NOW_EPOCH) / 86400 ))

                if [ $DAYS_LEFT -gt 30 ]; then
                    check_pass "Certificate valid for $DAYS_LEFT days"
                elif [ $DAYS_LEFT -gt 0 ]; then
                    check_warn "Certificate expiring soon ($DAYS_LEFT days left)"
                else
                    check_fail "Certificate EXPIRED"
                fi
            else
                check_warn "Could not check certificate expiry"
            fi

            # Check certificate issuer
            ISSUER=$(openssl x509 -in nginx/ssl/cert.pem -noout -issuer 2>/dev/null)
            if echo "$ISSUER" | grep -q "Let's Encrypt"; then
                check_pass "Certificate from Let's Encrypt (production)"
            else
                check_warn "Self-signed certificate (development only)"
            fi
        else
            check_warn "openssl not available - cannot verify certificate"
        fi
    else
        check_warn "SSL certificates not generated yet (run nginx/generate-ssl-dev.sh or generate-ssl-prod.sh)"
    fi
else
    check_warn "nginx/ssl directory not found (certificates not generated)"
fi

echo ""

# Check error pages
if [ -f "nginx/html/429.html" ]; then
    check_pass "Rate limit error page exists"
else
    check_warn "Rate limit error page (429.html) missing"
fi

if [ -f "nginx/html/50x.html" ]; then
    check_pass "Server error page exists"
else
    check_warn "Server error page (50x.html) missing"
fi

echo ""

# Check if containers are running (if Docker is available)
if command -v docker &> /dev/null; then
    echo "📋 Checking running containers..."
    echo ""

    if docker ps --format '{{.Names}}' | grep -q "eclaim-nginx"; then
        check_pass "nginx container is running"

        # Check if port 443 is exposed
        if docker ps --format '{{.Ports}}' --filter "name=eclaim-nginx" | grep -q "443"; then
            check_pass "Port 443 (HTTPS) is exposed"
        else
            check_fail "Port 443 (HTTPS) NOT exposed"
        fi

        # Check if port 80 is exposed
        if docker ps --format '{{.Ports}}' --filter "name=eclaim-nginx" | grep -q "80"; then
            check_pass "Port 80 (HTTP) is exposed"
        else
            check_warn "Port 80 (HTTP) NOT exposed (optional for redirect)"
        fi
    else
        check_warn "nginx container NOT running (start with: docker-compose -f docker-compose-https.yml up -d)"
    fi

    echo ""
fi

# Check app.py HTTPS configuration
if grep -q "WTF_CSRF_SSL_STRICT.*is_https" app.py; then
    check_pass "app.py configured for HTTPS detection"
else
    check_warn "app.py may not be configured for HTTPS"
fi

echo ""
echo "=================================="
echo "TEST SUMMARY"
echo "=================================="
echo ""
echo -e "${GREEN}Passed:${NC} $pass"
echo -e "${YELLOW}Warnings:${NC} $warn"
echo -e "${RED}Failed:${NC} $fail"
echo ""

if [ $fail -gt 0 ]; then
    echo -e "${RED}⚠️  HTTPS configuration has failures${NC}"
    echo ""
    echo "Fix the failures above before deploying to production"
    exit 1
elif [ $warn -gt 0 ]; then
    echo -e "${YELLOW}⚠️  HTTPS configuration has warnings${NC}"
    echo ""
    echo "Review the warnings above"
    echo ""
    echo "Next steps:"
    echo "  1. Generate SSL certificate:"
    echo "     - Development: cd nginx && ./generate-ssl-dev.sh"
    echo "     - Production:  cd nginx && DOMAIN=your.domain.com EMAIL=admin@domain.com ./generate-ssl-prod.sh"
    echo ""
    echo "  2. Start services:"
    echo "     docker-compose -f docker-compose-https.yml up -d"
    echo ""
    echo "  3. Test HTTPS:"
    echo "     curl -k https://localhost  # -k to accept self-signed cert"
    echo ""
else
    echo -e "${GREEN}✅ HTTPS configuration is ready!${NC}"
    echo ""
    echo "Test connection:"
    if [ -f "nginx/ssl/cert.pem" ]; then
        if grep -q "Let's Encrypt" <(openssl x509 -in nginx/ssl/cert.pem -noout -issuer 2>/dev/null); then
            echo "  Production: https://your-domain.com"
        else
            echo "  Development: https://localhost (accept self-signed cert warning)"
        fi
    fi
    echo ""
fi
