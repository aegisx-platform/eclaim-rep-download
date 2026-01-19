#!/bin/bash
# Renew Let's Encrypt SSL Certificate
# Run this script monthly via cron to auto-renew certificates

set -e

echo "=================================="
echo "Let's Encrypt Certificate Renewal"
echo "=================================="
echo ""
echo "Date: $(date)"
echo ""

# Check if certbot directory exists
if [ ! -d "certbot/conf" ]; then
    echo "❌ ERROR: certbot/conf directory not found"
    echo "   Certificates were not generated with generate-ssl-prod.sh"
    exit 1
fi

# Get domain from existing certificate
DOMAIN=$(ls certbot/conf/live/ 2>/dev/null | head -n 1)

if [ -z "$DOMAIN" ]; then
    echo "❌ ERROR: No certificates found in certbot/conf/live/"
    exit 1
fi

echo "📋 Certificate Info:"
echo "  Domain: $DOMAIN"
echo ""

# Check certificate expiry
EXPIRY_DATE=$(openssl x509 -in "ssl/cert.pem" -noout -enddate | cut -d= -f2)
EXPIRY_EPOCH=$(date -d "$EXPIRY_DATE" +%s 2>/dev/null || date -j -f "%b %d %H:%M:%S %Y %Z" "$EXPIRY_DATE" +%s)
NOW_EPOCH=$(date +%s)
DAYS_LEFT=$(( ($EXPIRY_EPOCH - $NOW_EPOCH) / 86400 ))

echo "  Current expiry: $EXPIRY_DATE"
echo "  Days remaining: $DAYS_LEFT"
echo ""

# Renew if less than 30 days remaining
if [ $DAYS_LEFT -gt 30 ]; then
    echo "✅ Certificate still valid for $DAYS_LEFT days"
    echo "   Renewal not needed (certificates are renewed 30 days before expiry)"
    echo ""
    exit 0
fi

echo "⚠️  Certificate expiring soon ($DAYS_LEFT days left)"
echo "📥 Renewing certificate..."
echo ""

# Stop nginx temporarily
docker-compose -f docker-compose-https.yml stop nginx

# Renew certificate
docker run --rm \
    -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
    -v "$(pwd)/certbot/www:/var/www/certbot" \
    -p 80:80 \
    certbot/certbot renew \
    --standalone \
    --non-interactive

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Certificate renewed successfully!"
    echo ""

    # Copy renewed certificates
    echo "📋 Copying renewed certificates..."
    cp "certbot/conf/live/$DOMAIN/fullchain.pem" ssl/cert.pem
    cp "certbot/conf/live/$DOMAIN/privkey.pem" ssl/key.pem
    chmod 600 ssl/key.pem
    chmod 644 ssl/cert.pem

    # Show new expiry date
    NEW_EXPIRY_DATE=$(openssl x509 -in "ssl/cert.pem" -noout -enddate | cut -d= -f2)
    echo "  New expiry: $NEW_EXPIRY_DATE"
    echo ""

    # Restart nginx
    echo "🔄 Restarting nginx..."
    docker-compose -f docker-compose-https.yml start nginx

    echo ""
    echo "✅ Certificate renewal complete!"
    echo ""
else
    echo ""
    echo "❌ Certificate renewal failed"
    echo ""
    echo "Restarting nginx with old certificate..."
    docker-compose -f docker-compose-https.yml start nginx
    exit 1
fi
