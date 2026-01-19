#!/bin/bash
# Generate Self-Signed SSL Certificate for Development
# DO NOT use this in production - use Let's Encrypt instead

set -e

echo "=================================="
echo "Generating Self-Signed SSL Certificate"
echo "=================================="
echo ""
echo "⚠️  WARNING: Self-signed certificates are for DEVELOPMENT ONLY"
echo "⚠️  For production, use Let's Encrypt (run generate-ssl-prod.sh)"
echo ""

# Create SSL directory if it doesn't exist
mkdir -p ssl

# Default values
COUNTRY="${SSL_COUNTRY:-TH}"
STATE="${SSL_STATE:-Bangkok}"
LOCALITY="${SSL_LOCALITY:-Bangkok}"
ORGANIZATION="${SSL_ORGANIZATION:-Hospital}"
ORGANIZATIONAL_UNIT="${SSL_OU:-IT Department}"
COMMON_NAME="${SSL_CN:-localhost}"
EMAIL="${SSL_EMAIL:-admin@localhost}"

# Days valid (default: 1 year)
DAYS="${SSL_DAYS:-365}"

echo "Certificate Information:"
echo "  Country: $COUNTRY"
echo "  State: $STATE"
echo "  Locality: $LOCALITY"
echo "  Organization: $ORGANIZATION"
echo "  Organizational Unit: $ORGANIZATIONAL_UNIT"
echo "  Common Name: $COMMON_NAME"
echo "  Email: $EMAIL"
echo "  Valid for: $DAYS days"
echo ""

# Generate private key and certificate
openssl req -x509 -nodes -days "$DAYS" \
    -newkey rsa:2048 \
    -keyout ssl/key.pem \
    -out ssl/cert.pem \
    -subj "/C=$COUNTRY/ST=$STATE/L=$LOCALITY/O=$ORGANIZATION/OU=$ORGANIZATIONAL_UNIT/CN=$COMMON_NAME/emailAddress=$EMAIL" \
    -addext "subjectAltName=DNS:$COMMON_NAME,DNS:localhost,IP:127.0.0.1"

# Set proper permissions
chmod 600 ssl/key.pem
chmod 644 ssl/cert.pem

echo ""
echo "✅ SSL certificate generated successfully!"
echo ""
echo "Files created:"
echo "  Private Key: ssl/key.pem"
echo "  Certificate: ssl/cert.pem"
echo ""
echo "Certificate details:"
openssl x509 -in ssl/cert.pem -noout -subject -dates -fingerprint
echo ""
echo "⚠️  Browser Security Warning:"
echo "  Your browser will show a security warning because this is a self-signed certificate."
echo "  This is expected in development. Click 'Advanced' → 'Proceed to site' to continue."
echo ""
echo "Next steps:"
echo "  1. Start services: docker-compose -f docker-compose-https.yml up -d"
echo "  2. Access via: https://localhost"
echo "  3. Accept browser security warning"
echo ""
