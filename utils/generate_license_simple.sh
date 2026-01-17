#!/bin/bash
# Simple License Generator using openssl (no Python dependencies needed)
# Usage: ./utils/generate_license_simple.sh

set -e

echo "======================================================================"
echo "🔐 NHSO Revenue Intelligence - Simple License Generator"
echo "======================================================================"
echo ""

# Create config directory if not exists
mkdir -p config

echo "🔑 Step 1: Generating RSA key pair..."
echo ""

# Generate private key (2048-bit RSA)
openssl genrsa -out config/license_test_private.pem 2048 2>/dev/null
echo "✅ Private key saved to: config/license_test_private.pem"

# Extract public key
openssl rsa -in config/license_test_private.pem -pubout -out config/license_test_public.pem 2>/dev/null
echo "✅ Public key saved to: config/license_test_public.pem"
echo ""

echo "======================================================================"
echo "📋 Next Steps:"
echo "======================================================================"
echo ""
echo "1️⃣  Install Python dependencies in Docker:"
echo "   docker-compose exec web pip install PyJWT==2.8.0 cryptography==41.0.7"
echo ""
echo "2️⃣  Generate license tokens:"
echo "   docker-compose exec web python utils/generate_test_license.py"
echo ""
echo "3️⃣  Install license via Web UI:"
echo "   - Open: http://localhost:5001/license"
echo "   - Copy license data from config/test_licenses.json"
echo "   - Paste into install form"
echo ""
echo "======================================================================"
echo "🔒 Security Reminder:"
echo "======================================================================"
echo ""
echo "⚠️  NEVER commit license_test_private.pem to git!"
echo "⚠️  Keep private key secure - only license issuer should have it"
echo "⚠️  Public key can be distributed safely to customers"
echo ""
echo "✅ RSA key pair generated successfully!"
echo ""
