# HTTPS Setup Guide

> Complete guide to deploying E-Claim System with HTTPS/TLS encryption

**Security Level:** 🔐 Production-Ready
**TLS Version:** TLSv1.2, TLSv1.3 (Modern)
**Date:** 2026-01-17

---

## Why HTTPS?

HTTPS (HTTP Secure) is **mandatory** for production deployment because:

1. **Encryption:** All traffic encrypted in transit (prevents eavesdropping)
2. **Authentication:** Verifies server identity (prevents man-in-the-middle attacks)
3. **Data Integrity:** Prevents data tampering
4. **PDPA Compliance:** Required for handling personal health information
5. **Browser Trust:** Modern browsers show warnings for HTTP sites
6. **Security Features:** Required for secure cookies, CSRF protection, HSTS

**Risk without HTTPS:**
- ❌ Passwords transmitted in plain text
- ❌ Session cookies vulnerable to hijacking
- ❌ Patient data exposed to network sniffing
- ❌ CSRF tokens can be intercepted
- ❌ Non-compliant with security standards

---

## Architecture

```
Internet
    ↓ HTTPS (443)
nginx reverse proxy
    ├── TLS termination (decrypt HTTPS)
    ├── Security headers
    ├── Rate limiting
    └── Proxy to Flask app (HTTP 5001)
        └── E-Claim Web UI
```

**Why nginx as reverse proxy?**
- Handles TLS/SSL efficiently
- Provides rate limiting and DDoS protection
- Adds security headers
- Serves static files directly
- Supports Let's Encrypt auto-renewal
- Production-grade web server

---

## Quick Start

### Development (Self-Signed Certificate)

```bash
# 1. Generate self-signed certificate
cd nginx
chmod +x generate-ssl-dev.sh
./generate-ssl-dev.sh

# 2. Start services
docker-compose -f docker-compose-https.yml up -d

# 3. Access via HTTPS
open https://localhost  # Accept security warning in browser
```

**Expected:** Browser shows security warning (expected for self-signed cert). Click "Advanced" → "Proceed to localhost".

### Production (Let's Encrypt Certificate)

```bash
# 1. Prerequisites
# - Domain name pointing to your server (e.g., eclaim.hospital.go.th)
# - Ports 80 and 443 open in firewall
# - Server accessible from internet

# 2. Generate Let's Encrypt certificate
cd nginx
chmod +x generate-ssl-prod.sh renew-ssl.sh
DOMAIN=eclaim.hospital.go.th EMAIL=admin@hospital.go.th ./generate-ssl-prod.sh

# 3. Start services
docker-compose -f docker-compose-https.yml up -d

# 4. Setup auto-renewal (cron)
crontab -e
# Add this line (runs monthly at midnight):
0 0 1 * * cd /path/to/eclaim && ./nginx/renew-ssl.sh >> /var/log/certbot-renew.log 2>&1

# 5. Access via HTTPS
open https://eclaim.hospital.go.th
```

---

## SSL Certificate Generation

### Self-Signed Certificate (Development)

**When to use:**
- Local development
- Internal testing
- Non-production environments

**Limitations:**
- Browser security warnings
- Not trusted by clients
- Not valid for production

**Generate:**

```bash
cd nginx
./generate-ssl-dev.sh

# Custom settings (optional)
SSL_CN=eclaim.local \
SSL_ORGANIZATION="My Hospital" \
SSL_DAYS=365 \
./generate-ssl-dev.sh
```

**Files created:**
- `nginx/ssl/cert.pem` - Public certificate
- `nginx/ssl/key.pem` - Private key (keep secret!)

**Verify certificate:**
```bash
openssl x509 -in nginx/ssl/cert.pem -text -noout
```

### Let's Encrypt Certificate (Production)

**When to use:**
- Production deployment
- Public-facing servers
- Domain with DNS configured

**Prerequisites:**
1. **Domain name** pointing to your server IP
2. **Port 80 open** (required for ACME challenge)
3. **Port 443 open** (HTTPS traffic)
4. **Server accessible** from internet

**Test with staging first:**

```bash
# Staging certificates (test setup without rate limits)
STAGING=true \
DOMAIN=eclaim.hospital.go.th \
EMAIL=admin@hospital.go.th \
./nginx/generate-ssl-prod.sh
```

**Generate production certificate:**

```bash
# Production certificates (real, trusted by browsers)
DOMAIN=eclaim.hospital.go.th \
EMAIL=admin@hospital.go.th \
./nginx/generate-ssl-prod.sh
```

**Rate limits:**
- 50 certificates per domain per week
- 5 duplicate certificates per week
- Always test with `STAGING=true` first!

**Certificate validity:**
- Valid for 90 days
- Auto-renewal recommended at 60 days
- Set up cron job for auto-renewal

---

## Auto-Renewal (Production Only)

Let's Encrypt certificates expire after 90 days. Set up auto-renewal:

### Option 1: Cron Job (Recommended)

```bash
# Edit crontab
crontab -e

# Add monthly renewal check (runs 1st of every month at midnight)
0 0 1 * * cd /path/to/eclaim-rep-download && ./nginx/renew-ssl.sh >> /var/log/certbot-renew.log 2>&1

# Or check/renew weekly (every Sunday at 3am)
0 3 * * 0 cd /path/to/eclaim-rep-download && ./nginx/renew-ssl.sh >> /var/log/certbot-renew.log 2>&1
```

### Option 2: systemd Timer

```bash
# Create systemd service
sudo nano /etc/systemd/system/certbot-renew.service

[Unit]
Description=Renew Let's Encrypt certificates
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/path/to/eclaim-rep-download
ExecStart=/path/to/eclaim-rep-download/nginx/renew-ssl.sh

# Create systemd timer
sudo nano /etc/systemd/system/certbot-renew.timer

[Unit]
Description=Renew Let's Encrypt certificates monthly

[Timer]
OnCalendar=monthly
Persistent=true

[Install]
WantedBy=timers.target

# Enable timer
sudo systemctl enable certbot-renew.timer
sudo systemctl start certbot-renew.timer

# Check status
sudo systemctl status certbot-renew.timer
```

### Manual Renewal

```bash
# Check certificate expiry
openssl x509 -in nginx/ssl/cert.pem -noout -dates

# Manually renew
./nginx/renew-ssl.sh
```

---

## nginx Configuration

The nginx configuration (`nginx/nginx.conf`) includes:

### Security Features

1. **Modern TLS:**
   - TLSv1.2, TLSv1.3 only (no SSLv3, TLSv1.0, TLSv1.1)
   - Strong cipher suites (ECDHE, AES-GCM, ChaCha20)
   - Perfect Forward Secrecy (PFS)

2. **Security Headers:**
   - `Strict-Transport-Security` (HSTS) - Force HTTPS for 2 years
   - `X-Frame-Options: SAMEORIGIN` - Prevent clickjacking
   - `X-Content-Type-Options: nosniff` - Prevent MIME sniffing
   - `X-XSS-Protection` - Browser XSS protection

3. **Rate Limiting:**
   - Login: 5 requests/minute (brute force protection)
   - API: 30 requests/minute
   - General: 100 requests/minute

4. **OCSP Stapling:**
   - Faster certificate validation
   - Privacy enhancement

### HTTP to HTTPS Redirect

All HTTP traffic (port 80) is redirected to HTTPS (port 443):

```nginx
server {
    listen 80;
    server_name _;

    # Allow Let's Encrypt challenges
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    # Redirect everything else to HTTPS
    location / {
        return 301 https://$host$request_uri;
    }
}
```

---

## Docker Compose Configuration

`docker-compose-https.yml` includes:

```yaml
services:
  nginx:
    image: nginx:1.25-alpine
    ports:
      - "80:80"    # HTTP (redirects to HTTPS)
      - "443:443"  # HTTPS
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - ./nginx/html:/usr/share/nginx/html:ro

  web:
    environment:
      # HTTPS mode enabled
      WTF_CSRF_SSL_STRICT: "true"
      SESSION_COOKIE_SECURE: "true"
      SESSION_COOKIE_HTTPONLY: "true"
      SESSION_COOKIE_SAMESITE: "Lax"
```

**Key differences from HTTP:**
- nginx service added
- Ports 80 and 443 exposed
- HTTPS-specific environment variables
- Secure cookie settings

---

## Flask App Configuration

When HTTPS is enabled, Flask automatically configures:

```python
# app.py detects HTTPS mode from environment
is_https = os.environ.get('WTF_CSRF_SSL_STRICT', 'false').lower() == 'true'

if is_https:
    app.config['WTF_CSRF_SSL_STRICT'] = True  # CSRF tokens only via HTTPS
    app.config['SESSION_COOKIE_SECURE'] = True  # Session cookies only via HTTPS
    app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent JS access
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection
```

**What this does:**
- CSRF tokens only sent over HTTPS
- Session cookies only sent over HTTPS
- Cookies inaccessible to JavaScript (XSS protection)
- SameSite protection against CSRF attacks

---

## Testing

### Test HTTPS Setup

```bash
# Run automated tests
chmod +x test_https.sh
./test_https.sh
```

**Expected output:**
```
================================
HTTPS CONFIGURATION TEST
================================

✓ nginx.conf exists
✓ Modern SSL protocols configured
✓ HSTS enabled
✓ Security headers configured
✓ Rate limiting configured
...
✅ HTTPS configuration is ready!
```

### Manual Testing

**1. Test HTTPS Connection:**
```bash
# Self-signed certificate (development)
curl -k https://localhost

# Production certificate
curl https://eclaim.hospital.go.th
```

**2. Test HTTP to HTTPS Redirect:**
```bash
curl -I http://localhost
# Expected: 301 Moved Permanently
# Location: https://localhost/
```

**3. Test Security Headers:**
```bash
curl -I https://localhost
# Expected headers:
# Strict-Transport-Security: max-age=63072000
# X-Frame-Options: SAMEORIGIN
# X-Content-Type-Options: nosniff
```

**4. Test Rate Limiting:**
```bash
# Login endpoint (5 req/min)
for i in {1..10}; do curl -X POST https://localhost/login; done
# Expected: 429 Too Many Requests after 5 attempts
```

**5. Test SSL/TLS Configuration:**
```bash
# SSL Labs (online test for production)
# https://www.ssllabs.com/ssltest/analyze.html?d=eclaim.hospital.go.th

# OpenSSL test
openssl s_client -connect localhost:443 -tls1_3
openssl s_client -connect localhost:443 -tls1_2
openssl s_client -connect localhost:443 -tls1_1  # Should fail
```

**6. Test Certificate Chain:**
```bash
openssl s_client -connect localhost:443 -showcerts
```

---

## Troubleshooting

### Issue: Browser shows "Your connection is not private"

**Cause:** Using self-signed certificate (development)

**Solution:**
- Development: Click "Advanced" → "Proceed to localhost"
- Production: Use Let's Encrypt certificate instead

### Issue: Certificate generation fails

**Common causes:**
1. **Domain not resolving**
   ```bash
   # Check DNS
   nslookup eclaim.hospital.go.th
   host eclaim.hospital.go.th
   ```

2. **Port 80 blocked**
   ```bash
   # Check firewall
   sudo ufw status
   sudo iptables -L -n
   ```

3. **Rate limit reached**
   - Solution: Wait 1 week or use staging environment

4. **Email invalid**
   - Verify email format and domain

### Issue: Auto-renewal not working

**Check:**
```bash
# Verify cron job exists
crontab -l | grep certbot

# Check logs
tail -f /var/log/certbot-renew.log

# Test renewal manually
./nginx/renew-ssl.sh
```

### Issue: nginx fails to start

**Check:**
```bash
# View nginx logs
docker-compose -f docker-compose-https.yml logs nginx

# Test nginx config
docker run --rm -v $(pwd)/nginx/nginx.conf:/etc/nginx/nginx.conf:ro nginx:1.25-alpine nginx -t

# Common errors:
# - SSL certificate files missing
# - Invalid nginx.conf syntax
# - Port 443 already in use
```

### Issue: "CSRF validation failed" after enabling HTTPS

**Cause:** Browser cached HTTP cookies

**Solution:**
```bash
# Clear browser cookies for the site
# Or use incognito/private mode for testing
```

---

## Security Best Practices

### Certificate Management

1. **Keep private key secure:**
   ```bash
   chmod 600 nginx/ssl/key.pem  # Owner read/write only
   ```

2. **Backup certificates:**
   ```bash
   # Backup Let's Encrypt data
   tar -czf certbot-backup-$(date +%Y%m%d).tar.gz certbot/
   ```

3. **Monitor expiry:**
   ```bash
   # Check expiry date
   openssl x509 -in nginx/ssl/cert.pem -noout -dates

   # Set up monitoring alerts (Nagios, Zabbix, etc.)
   ```

4. **Rotate on compromise:**
   - If private key is compromised, revoke and reissue immediately

### nginx Security

1. **Keep nginx updated:**
   ```bash
   # Pull latest stable image
   docker pull nginx:1.25-alpine
   docker-compose -f docker-compose-https.yml up -d nginx
   ```

2. **Review security headers regularly:**
   - Test with securityheaders.com
   - Test with observatory.mozilla.org

3. **Monitor rate limit logs:**
   ```bash
   docker-compose -f docker-compose-https.yml logs nginx | grep "limiting requests"
   ```

### Firewall Configuration

**Required ports:**
```bash
# Allow HTTPS
sudo ufw allow 443/tcp comment 'HTTPS'

# Allow HTTP (for Let's Encrypt challenges and redirect)
sudo ufw allow 80/tcp comment 'HTTP redirect'

# Block direct access to Flask app (port 5001)
# Should only be accessible from nginx container
```

---

## Production Checklist

Before deploying to production:

- [ ] Domain DNS configured
- [ ] Firewall allows ports 80 and 443
- [ ] Let's Encrypt production certificate generated (not staging)
- [ ] Auto-renewal cron job configured
- [ ] HSTS enabled in nginx.conf
- [ ] Security headers configured
- [ ] Rate limiting tested
- [ ] HTTP to HTTPS redirect working
- [ ] SSL Labs test shows A+ rating
- [ ] Certificate expiry monitoring set up
- [ ] Backup procedures in place
- [ ] Private key permissions set to 600
- [ ] `WTF_CSRF_SSL_STRICT=true` in environment
- [ ] Session cookies secure
- [ ] Test login/logout over HTTPS
- [ ] Test all API endpoints over HTTPS

---

## Performance Optimization

### HTTP/2 Support

nginx.conf already enables HTTP/2:
```nginx
listen 443 ssl http2;
```

**Benefits:**
- Faster page loads (multiplexing)
- Header compression
- Server push support

### SSL Session Caching

```nginx
ssl_session_timeout 1d;
ssl_session_cache shared:SSL:50m;
```

**Benefits:**
- Faster reconnects (session resumption)
- Reduced CPU usage on server

### OCSP Stapling

```nginx
ssl_stapling on;
ssl_stapling_verify on;
```

**Benefits:**
- Faster certificate validation
- Reduced latency
- Privacy (no OCSP server contact)

---

## Monitoring

### Certificate Expiry

```bash
# Check days until expiry
openssl x509 -in nginx/ssl/cert.pem -noout -checkend 2592000
# Exit code 0 = valid for at least 30 days
# Exit code 1 = expires within 30 days
```

### HTTPS Traffic

```bash
# Monitor HTTPS connections
docker-compose -f docker-compose-https.yml logs -f nginx

# Count HTTPS requests
docker-compose -f docker-compose-https.yml logs nginx | grep "HTTPS" | wc -l
```

### SSL/TLS Errors

```bash
# Check for SSL handshake errors
docker-compose -f docker-compose-https.yml logs nginx | grep "SSL"
```

---

## Migration from HTTP to HTTPS

### Step-by-Step Migration

1. **Test HTTPS in staging:**
   ```bash
   # Use self-signed cert for testing
   cd nginx && ./generate-ssl-dev.sh
   docker-compose -f docker-compose-https.yml up -d
   # Test thoroughly
   ```

2. **Schedule maintenance window:**
   - Notify users of brief downtime
   - Choose low-traffic time

3. **Generate production certificate:**
   ```bash
   cd nginx
   DOMAIN=your.domain.com EMAIL=admin@domain.com ./generate-ssl-prod.sh
   ```

4. **Switch to HTTPS:**
   ```bash
   # Stop HTTP version
   docker-compose down

   # Start HTTPS version
   docker-compose -f docker-compose-https.yml up -d
   ```

5. **Update DNS (if needed):**
   - Ensure domain points to server
   - Update CDN or load balancer

6. **Enable HSTS:**
   - After verifying HTTPS works for 24 hours
   - Prevents downgrade attacks

7. **Monitor:**
   - Check logs for errors
   - Monitor certificate expiry
   - Test auto-renewal

---

## Resources

- **Let's Encrypt:** https://letsencrypt.org/
- **SSL Labs Test:** https://www.ssllabs.com/ssltest/
- **Mozilla SSL Config:** https://ssl-config.mozilla.org/
- **Security Headers:** https://securityheaders.com/
- **OWASP TLS Cheat Sheet:** https://cheatsheetseries.owasp.org/cheatsheets/Transport_Layer_Protection_Cheat_Sheet.html

---

**Last Updated:** 2026-01-17
**Maintainer:** Security Team

**Next:** [Security Audit](SECURITY_AUDIT.md) | [Production Deployment](PRODUCTION_DEPLOYMENT.md)
