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

    # Tier features (must match license_checker.py)
    tier_features = {
        'free': {
            'tier_name': 'Free',
            'price_per_year': 0,
            'max_users': 9999,
            'max_records_per_import': 9999999,
            'data_retention_years': 999,
            'smt_budget': True,
            'rep_access': False,
            'stm_access': False,
            'view_reports': True,
            'export_reports': True,
            'analytics_basic': True,
            'analytics_advanced': False,
            'reconciliation': False,
            'api_access': False,
            'custom_reports': False,
            'scheduled_downloads': False,
            'white_label': False,
            'priority_support': False,
            'dedicated_support': False,
            'custom_development': False,
            'sla_guarantee': False
        },
        'basic': {
            'tier_name': 'Basic',
            'price_per_year': 10000,
            'max_users': 10,
            'max_records_per_import': 9999999,
            'data_retention_years': 3,
            'smt_budget': True,
            'rep_access': True,
            'stm_access': True,
            'view_reports': True,
            'export_reports': True,
            'analytics_basic': True,
            'analytics_advanced': False,
            'reconciliation': False,
            'api_access': False,
            'custom_reports': False,
            'scheduled_downloads': True,
            'white_label': False,
            'priority_support': False,
            'dedicated_support': False,
            'custom_development': False,
            'sla_guarantee': False
        },
        'professional': {
            'tier_name': 'Professional',
            'price_per_year': 30000,
            'max_users': 50,
            'max_records_per_import': 9999999,
            'data_retention_years': 5,
            'smt_budget': True,
            'rep_access': True,
            'stm_access': True,
            'view_reports': True,
            'export_reports': True,
            'analytics_basic': True,
            'analytics_advanced': True,
            'reconciliation': True,
            'api_access': True,
            'custom_reports': True,
            'scheduled_downloads': True,
            'white_label': False,
            'priority_support': True,
            'dedicated_support': False,
            'custom_development': False,
            'sla_guarantee': False
        },
        'enterprise': {
            'tier_name': 'Enterprise',
            'price_per_year': 100000,
            'max_users': 9999,
            'max_records_per_import': 9999999,
            'data_retention_years': 999,
            'smt_budget': True,
            'rep_access': True,
            'stm_access': True,
            'view_reports': True,
            'export_reports': True,
            'analytics_basic': True,
            'analytics_advanced': True,
            'reconciliation': True,
            'api_access': True,
            'custom_reports': True,
            'scheduled_downloads': True,
            'white_label': True,
            'priority_support': True,
            'dedicated_support': True,
            'custom_development': True,
            'sla_guarantee': True,
            'multi_site': True
        }
    }

    license_key = generate_license_key()

    # Build JWT payload
    from datetime import timezone
    now = datetime.now(timezone.utc)
    payload = {
        'license_key': license_key,
        'hospital_code': hospital_code,
        'hospital_name': hospital_name,
        'tier': tier,
        'license_type': 'perpetual' if days_valid is None else 'subscription',
        'features': tier_features.get(tier, tier_features['free']),
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
    print("🔐 Revenue Intelligence System - Test License Generator")
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

    # 1. Free License (Perpetual - SMT only)
    print("1️⃣  Free License (Perpetual)")
    key, token = generate_license_token(
        private_key,
        tier='free',
        hospital_code='10001',
        hospital_name='โรงพยาบาลทดสอบ',
        days_valid=None  # Perpetual
    )
    licenses['free'] = {
        'license_key': key,
        'license_token': token,
        'public_key': public_key,
        'tier': 'free',
        'price': '0 บาท',
        'expires': 'Never (Perpetual)'
    }
    print(f"   License Key: {key}")
    print(f"   Tier: Free (0 บาท/year)")
    print(f"   Features: SMT Budget only, View Reports (read-only)")
    print(f"   Limits: Unlimited users, Unlimited retention")
    print(f"   Expires: Never (Perpetual)\n")

    # 2. Basic License (1 year - 10,000 บาท)
    print("2️⃣  Basic License (1 year)")
    key, token = generate_license_token(
        private_key,
        tier='basic',
        hospital_code='10670',
        hospital_name='โรงพยาบาลขอนแก่น',
        days_valid=365
    )
    licenses['basic'] = {
        'license_key': key,
        'license_token': token,
        'public_key': public_key,
        'tier': 'basic',
        'price': '10,000 บาท/year',
        'expires': '1 year from now'
    }
    print(f"   License Key: {key}")
    print(f"   Tier: Basic (10,000 บาท/year)")
    print(f"   Features: REP + STM + SMT, Basic Analytics, Auto Download")
    print(f"   Limits: 10 users, 3 years retention")
    print(f"   Expires: 1 year from now\n")

    # 3. Professional License (1 year - 30,000 บาท)
    print("3️⃣  Professional License (1 year)")
    key, token = generate_license_token(
        private_key,
        tier='professional',
        hospital_code='10670',
        hospital_name='โรงพยาบาลขอนแก่น',
        days_valid=365
    )
    licenses['professional'] = {
        'license_key': key,
        'license_token': token,
        'public_key': public_key,
        'tier': 'professional',
        'price': '30,000 บาท/year',
        'expires': '1 year from now'
    }
    print(f"   License Key: {key}")
    print(f"   Tier: Professional (30,000 บาท/year)")
    print(f"   Features: Advanced Analytics, HIS Reconciliation, API Access")
    print(f"   Limits: 50 users, 5 years retention")
    print(f"   Expires: 1 year from now\n")

    # 4. Enterprise License (1 year - 100,000 บาท)
    print("4️⃣  Enterprise License (1 year)")
    key, token = generate_license_token(
        private_key,
        tier='enterprise',
        hospital_code='10670',
        hospital_name='โรงพยาบาลขอนแก่น',
        days_valid=365
    )
    licenses['enterprise'] = {
        'license_key': key,
        'license_token': token,
        'public_key': public_key,
        'tier': 'enterprise',
        'price': '100,000 บาท/year',
        'expires': '1 year from now'
    }
    print(f"   License Key: {key}")
    print(f"   Tier: Enterprise (100,000 บาท/year)")
    print(f"   Features: White Label, Dedicated Support, Custom Development")
    print(f"   Limits: Unlimited users, Unlimited retention")
    print(f"   Expires: 1 year from now\n")

    # 5. Expiring Soon License (15 days - for testing warning)
    print("5️⃣  Expiring Soon License (15 days - for testing warning)")
    key, token = generate_license_token(
        private_key,
        tier='professional',
        hospital_code='10670',
        hospital_name='โรงพยาบาลขอนแก่น',
        days_valid=15
    )
    licenses['expiring_soon'] = {
        'license_key': key,
        'license_token': token,
        'public_key': public_key,
        'tier': 'professional',
        'price': '30,000 บาท/year',
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
        hospital_name='โรงพยาบาลขอนแก่น',
        days_valid=-5  # Already expired
    )
    licenses['expired'] = {
        'license_key': key,
        'license_token': token,
        'public_key': public_key,
        'tier': 'professional',
        'price': '30,000 บาท/year',
        'expires': '5 days ago (Grace period active)'
    }
    print(f"   License Key: {key}")
    print(f"   Tier: Professional")
    print(f"   Expires: 5 days ago (Grace period - 90 days left)\n")

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
    print("💰 Pricing Tiers:")
    print("   • Free: 0 บาท - SMT only, read-only reports")
    print("   • Basic: 10,000 บาท/year - REP + STM + SMT, 10 users")
    print("   • Professional: 30,000 บาท/year - Advanced analytics, API, 50 users")
    print("   • Enterprise: 100,000 บาท/year - White label, unlimited users")
    print()
    print("💡 Try different tiers to test feature restrictions!")
    print()


if __name__ == '__main__':
    main()
