#!/usr/bin/env python3
"""
Generate Test License Tokens
Generate sample JWT license tokens for testing the license system
"""

import jwt
from datetime import datetime, timedelta
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import json


def generate_rsa_keypair():
    """Generate RSA key pair for signing"""
    print("🔑 Generating RSA key pair...")

    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )

    # Get public key
    public_key = private_key.public_key()

    # Serialize private key to PEM format
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')

    # Serialize public key to PEM format
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')

    return private_pem, public_pem


def generate_license_key(prefix='REVINT'):
    """Generate a license key"""
    import random
    import string

    part1 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    part2 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

    return f'{prefix}-{part1}-{part2}'


def generate_license_token(private_key_pem, tier='professional', hospital_code='10670',
                           hospital_name='โรงพยาบาลทดสอบ', days_valid=365):
    """
    Generate a license token

    Args:
        private_key_pem: RSA private key in PEM format
        tier: License tier (trial, basic, professional, enterprise)
        hospital_code: 5-digit hospital code
        hospital_name: Hospital name
        days_valid: Number of days the license is valid (None for perpetual)

    Returns:
        (license_key, license_token)
    """

    # Tier features
    tier_features = {
        'trial': {
            'max_users': 2,
            'max_records_per_import': 1000,
            'smt_budget': False,
            'analytics_advanced': False,
            'reconciliation': False,
            'api_access': False,
            'priority_support': False,
            'custom_reports': False
        },
        'basic': {
            'max_users': 5,
            'max_records_per_import': 50000,
            'smt_budget': True,
            'analytics_advanced': False,
            'reconciliation': True,
            'api_access': False,
            'priority_support': False,
            'custom_reports': False
        },
        'professional': {
            'max_users': 20,
            'max_records_per_import': 500000,
            'smt_budget': True,
            'analytics_advanced': True,
            'reconciliation': True,
            'api_access': True,
            'priority_support': True,
            'custom_reports': True
        },
        'enterprise': {
            'max_users': 9999,
            'max_records_per_import': 9999999,
            'smt_budget': True,
            'analytics_advanced': True,
            'reconciliation': True,
            'api_access': True,
            'priority_support': True,
            'custom_reports': True,
            'white_label': True,
            'dedicated_support': True
        }
    }

    license_key = generate_license_key()

    # Build JWT payload
    now = datetime.utcnow()
    payload = {
        'license_key': license_key,
        'hospital_code': hospital_code,
        'hospital_name': hospital_name,
        'tier': tier,
        'license_type': 'perpetual' if days_valid is None else 'subscription',
        'features': tier_features.get(tier, tier_features['trial']),
        'iat': int(now.timestamp()),
        'max_users': tier_features.get(tier, {}).get('max_users', 2),
        'limits': {
            'max_records_per_import': tier_features.get(tier, {}).get('max_records_per_import', 1000)
        }
    }

    # Add expiration if not perpetual
    if days_valid is not None:
        exp_date = now + timedelta(days=days_valid)
        payload['exp'] = int(exp_date.timestamp())

    # Load private key
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode('utf-8'),
        password=None,
        backend=default_backend()
    )

    # Sign JWT with RS256
    token = jwt.encode(payload, private_key, algorithm='RS256')

    return license_key, token


def main():
    print("=" * 70)
    print("🔐 NHSO Revenue Intelligence - Test License Generator")
    print("=" * 70)
    print()

    # Generate RSA key pair
    private_key, public_key = generate_rsa_keypair()
    print("✅ RSA key pair generated\n")

    # Save keys to files
    with open('config/license_test_private.pem', 'w') as f:
        f.write(private_key)
    print("📝 Private key saved to: config/license_test_private.pem")

    with open('config/license_test_public.pem', 'w') as f:
        f.write(public_key)
    print("📝 Public key saved to: config/license_test_public.pem")
    print()

    # Generate test licenses for all tiers
    licenses = {}

    print("🎫 Generating test licenses...\n")

    # 1. Trial License (30 days)
    print("1️⃣  Trial License (30 days)")
    key, token = generate_license_token(
        private_key,
        tier='trial',
        hospital_code='10001',
        hospital_name='โรงพยาบาลทดลอง',
        days_valid=30
    )
    licenses['trial'] = {
        'license_key': key,
        'license_token': token,
        'public_key': public_key,
        'tier': 'trial',
        'expires': '30 days from now'
    }
    print(f"   License Key: {key}")
    print(f"   Tier: Trial (2 users, 1,000 records/import)")
    print(f"   Expires: 30 days from now\n")

    # 2. Basic License (1 year)
    print("2️⃣  Basic License (1 year)")
    key, token = generate_license_token(
        private_key,
        tier='basic',
        hospital_code='10670',
        hospital_name='โรงพยาบาลศิริราช',
        days_valid=365
    )
    licenses['basic'] = {
        'license_key': key,
        'license_token': token,
        'public_key': public_key,
        'tier': 'basic',
        'expires': '1 year from now'
    }
    print(f"   License Key: {key}")
    print(f"   Tier: Basic (5 users, 50,000 records/import)")
    print(f"   Expires: 1 year from now\n")

    # 3. Professional License (1 year)
    print("3️⃣  Professional License (1 year)")
    key, token = generate_license_token(
        private_key,
        tier='professional',
        hospital_code='10670',
        hospital_name='โรงพยาบาลศิริราช',
        days_valid=365
    )
    licenses['professional'] = {
        'license_key': key,
        'license_token': token,
        'public_key': public_key,
        'tier': 'professional',
        'expires': '1 year from now'
    }
    print(f"   License Key: {key}")
    print(f"   Tier: Professional (20 users, 500,000 records/import)")
    print(f"   Expires: 1 year from now\n")

    # 4. Enterprise License (Perpetual)
    print("4️⃣  Enterprise License (Perpetual)")
    key, token = generate_license_token(
        private_key,
        tier='enterprise',
        hospital_code='10670',
        hospital_name='โรงพยาบาลศิริราช',
        days_valid=None  # Perpetual
    )
    licenses['enterprise'] = {
        'license_key': key,
        'license_token': token,
        'public_key': public_key,
        'tier': 'enterprise',
        'expires': 'Never (Perpetual)'
    }
    print(f"   License Key: {key}")
    print(f"   Tier: Enterprise (Unlimited users & records)")
    print(f"   Expires: Never (Perpetual)\n")

    # 5. Expiring Soon License (15 days)
    print("5️⃣  Expiring Soon License (15 days - for testing warning)")
    key, token = generate_license_token(
        private_key,
        tier='professional',
        hospital_code='10670',
        hospital_name='โรงพยาบาลศิริราช',
        days_valid=15
    )
    licenses['expiring_soon'] = {
        'license_key': key,
        'license_token': token,
        'public_key': public_key,
        'tier': 'professional',
        'expires': '15 days from now'
    }
    print(f"   License Key: {key}")
    print(f"   Tier: Professional")
    print(f"   Expires: 15 days from now (Will show warning)\n")

    # 6. Expired License (grace period test)
    print("6️⃣  Expired License (-5 days - for testing grace period)")
    key, token = generate_license_token(
        private_key,
        tier='professional',
        hospital_code='10670',
        hospital_name='โรงพยาบาลศิริราช',
        days_valid=-5  # Already expired
    )
    licenses['expired'] = {
        'license_key': key,
        'license_token': token,
        'public_key': public_key,
        'tier': 'professional',
        'expires': '5 days ago (Grace period active)'
    }
    print(f"   License Key: {key}")
    print(f"   Tier: Professional")
    print(f"   Expires: 5 days ago (Grace period - 2 days left)\n")

    # Save all licenses to JSON file
    output_file = 'config/test_licenses.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(licenses, f, ensure_ascii=False, indent=2)

    print("=" * 70)
    print(f"✅ All test licenses saved to: {output_file}")
    print("=" * 70)
    print()
    print("📖 How to use:")
    print()
    print("1. Open the web UI: http://localhost:5001/license")
    print("2. Go to 'Install / Update License' section")
    print("3. Copy the license_key, license_token, and public_key from test_licenses.json")
    print("4. Paste into the form and click 'Install License'")
    print()
    print("💡 Try different tiers to test feature restrictions!")
    print()


if __name__ == '__main__':
    main()
