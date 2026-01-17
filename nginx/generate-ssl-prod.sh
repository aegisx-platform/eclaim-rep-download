#!/bin/bash
# Generate Let's Encrypt SSL Certificate for Production
# Uses Certbot in Docker to obtain free SSL certificates

set -e

echo "=================================="
echo "Let's Encrypt SSL Certificate Setup"
echo "=================================="
echo ""

# Check required environment variables
if [ -z "$DOMAIN" ]; then
    echo "❌ ERROR: DOMAIN environment variable is required"
    echo ""
    echo "Usage:"
    echo "  DOMAIN=eclaim.yourhospital.com EMAIL=admin@yourhospital.com ./generate-ssl-prod.sh"
    echo ""
    echo "Environment variables:"
    echo "  DOMAIN (required)  - Your domain name (e.g., eclaim.hospital.go.th)"
    echo "  EMAIL (required)   - Email for Let's Encrypt notifications"
    echo "  STAGING (optional) - Set to 'true' for testing (default: false)"
    echo ""
    exit 1
fi

if [ -z "$EMAIL" ]; then
    echo "❌ ERROR: EMAIL environment variable is required"
    exit 1
fi

STAGING="${STAGING:-false}"

echo "Configuration:"
echo "  Domain: $DOMAIN"
echo "  Email: $EMAIL"
echo "  Staging Mode: $STAGING"
echo ""

# Create directories
mkdir -p ssl
mkdir -p certbot/www
mkdir -p certbot/conf

echo "📋 Prerequisites Check:"
echo ""

# Check if domain is accessible
echo "1. Checking if domain resolves..."
if ! host "$DOMAIN" > /dev/null 2>&1; then
    echo "   ⚠️  WARNING: Domain '$DOMAIN' does not resolve to an IP"
    echo "   Make sure DNS is configured before proceeding"
    read -p "   Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "   ✅ Domain resolves"
fi

# Check if port 80 is accessible
echo "2. Checking port 80 availability..."
echo "   ⚠️  Port 80 must be accessible from the internet for Let's Encrypt validation"
echo "   ⚠️  Make sure firewall allows HTTP (port 80) and HTTPS (port 443)"
echo ""

# Staging or production
CERTBOT_ARGS=""
if [ "$STAGING" = "true" ]; then
    echo "🧪 Running in STAGING mode (test certificates)"
    echo "   Certificates will NOT be trusted by browsers"
    echo "   Use this to test setup before requesting real certificates"
    CERTBOT_ARGS="--staging"
else
    echo "🔐 Running in PRODUCTION mode (real certificates)"
    echo "   ⚠️  Let's Encrypt rate limits:"
    echo "      - 50 certificates per domain per week"
    echo "      - 5 duplicate certificates per week"
    echo "   Test with STAGING=true first!"
    echo ""
    read -p "   Proceed with production certificate request? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo "📥 Obtaining SSL certificate from Let's Encrypt..."
echo ""

# Stop nginx if running (to free port 80)
docker-compose -f docker-compose-https.yml stop nginx 2>/dev/null || true

# Run certbot in standalone mode
docker run --rm \
    -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
    -v "$(pwd)/certbot/www:/var/www/certbot" \
    -p 80:80 \
    certbot/certbot certonly \
    --standalone \
    --non-interactive \
    --agree-tos \
    --email "$EMAIL" \
    -d "$DOMAIN" \
    $CERTBOT_ARGS

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Certificate obtained successfully!"
    echo ""

    # Copy certificates to nginx ssl directory
    echo "📋 Copying certificates to nginx/ssl/..."
    cp "certbot/conf/live/$DOMAIN/fullchain.pem" ssl/cert.pem
    cp "certbot/conf/live/$DOMAIN/privkey.pem" ssl/key.pem
    chmod 600 ssl/key.pem
    chmod 644 ssl/cert.pem

    echo ""
    echo "Certificate details:"
    openssl x509 -in ssl/cert.pem -noout -subject -dates -issuer
    echo ""

    if [ "$STAGING" = "true" ]; then
        echo "🧪 STAGING certificate created"
        echo ""
        echo "Next steps:"
        echo "  1. If testing was successful, run again without STAGING=true"
        echo "  2. STAGING=false DOMAIN=$DOMAIN EMAIL=$EMAIL ./generate-ssl-prod.sh"
    else
        echo "🎉 Production certificate ready!"
        echo ""
        echo "Next steps:"
        echo "  1. Start services: docker-compose -f docker-compose-https.yml up -d"
        echo "  2. Access via: https://$DOMAIN"
        echo ""
        echo "📅 Certificate Auto-Renewal:"
        echo "  Certificates expire in 90 days"
        echo "  Set up auto-renewal with cron:"
        echo ""
        echo "  # Add to crontab (crontab -e):"
        echo "  0 0 * * * cd /path/to/eclaim && ./nginx/renew-ssl.sh >> /var/log/certbot-renew.log 2>&1"
        echo ""
    fi
else
    echo ""
    echo "❌ Failed to obtain certificate"
    echo ""
    echo "Common issues:"
    echo "  1. Domain not pointing to this server's IP"
    echo "  2. Firewall blocking port 80"
    echo "  3. Rate limit reached (try STAGING=true first)"
    echo "  4. Email address invalid"
    echo ""
    echo "Check certbot logs for details"
    exit 1
fi
