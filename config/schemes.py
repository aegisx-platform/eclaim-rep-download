"""
Insurance Schemes Configuration for E-Claim Downloader

Defines all available NHSO insurance schemes (สิทธิการรักษา)
for the Thai National Health Security Office system.
"""

# All available insurance schemes
INSURANCE_SCHEMES = {
    'ucs': {
        'code': 'ucs',
        'name_th': 'สิทธิหลักประกันสุขภาพถ้วนหน้า',
        'name_en': 'Universal Coverage Scheme',
        'short_name': 'บัตรทอง',
        'enabled_default': True,
        'priority': 1
    },
    'ofc': {
        'code': 'ofc',
        'name_th': 'สิทธิข้าราชการ',
        'name_en': 'Government Officer',
        'short_name': 'ข้าราชการ',
        'enabled_default': True,
        'priority': 2
    },
    'sss': {
        'code': 'sss',
        'name_th': 'สิทธิประกันสังคม',
        'name_en': 'Social Security Scheme',
        'short_name': 'ประกันสังคม',
        'enabled_default': True,
        'priority': 3
    },
    'lgo': {
        'code': 'lgo',
        'name_th': 'สิทธิกองทุนบุคลากรองค์การปกครองส่วนท้องถิ่น',
        'name_en': 'Local Government Organization',
        'short_name': 'อปท.',
        'enabled_default': True,
        'priority': 4
    },
    'nhs': {
        'code': 'nhs',
        'name_th': 'สิทธิเจ้าหน้าที่สปสช.',
        'name_en': 'NHSO Staff',
        'short_name': 'สปสช.',
        'enabled_default': False,
        'priority': 5
    },
    'bkk': {
        'code': 'bkk',
        'name_th': 'สิทธิเจ้าหน้าที่กรุงเทพมหานคร',
        'name_en': 'Bangkok Metropolitan Staff',
        'short_name': 'กทม.',
        'enabled_default': False,
        'priority': 6
    },
    'bmt': {
        'code': 'bmt',
        'name_th': 'สิทธิเจ้าหน้าที่ขสมก.',
        'name_en': 'BMTA Staff',
        'short_name': 'ขสมก.',
        'enabled_default': False,
        'priority': 7
    },
    'srt': {
        'code': 'srt',
        'name_th': 'เจ้าหน้าที่การรถไฟแห่งประเทศไทย',
        'name_en': 'State Railway of Thailand Staff',
        'short_name': 'รฟท.',
        'enabled_default': False,
        'priority': 8
    }
}

# Default enabled schemes (main 4 schemes)
DEFAULT_ENABLED_SCHEMES = ['ucs', 'ofc', 'sss', 'lgo']


def get_all_schemes():
    """
    Get all available insurance schemes

    Returns:
        dict: All schemes with their configuration
    """
    return INSURANCE_SCHEMES.copy()


def get_scheme_by_code(code):
    """
    Get scheme details by code

    Args:
        code (str): Scheme code (e.g., 'ucs', 'ofc')

    Returns:
        dict: Scheme details or None if not found
    """
    return INSURANCE_SCHEMES.get(code)


def get_default_enabled_schemes():
    """
    Get list of default enabled scheme codes

    Returns:
        list: List of scheme codes that are enabled by default
    """
    return DEFAULT_ENABLED_SCHEMES.copy()


def get_enabled_schemes_from_settings(settings_manager=None):
    """
    Get list of enabled schemes from settings
    Falls back to default if not configured

    Args:
        settings_manager: Optional SettingsManager instance

    Returns:
        list: List of enabled scheme codes
    """
    if settings_manager:
        enabled = settings_manager.get_setting('enabled_schemes')
        if enabled:
            return enabled
    return get_default_enabled_schemes()


def get_schemes_sorted_by_priority(scheme_codes=None):
    """
    Get schemes sorted by priority

    Args:
        scheme_codes (list, optional): List of scheme codes to sort.
                                      If None, returns all schemes.

    Returns:
        list: List of scheme dicts sorted by priority
    """
    if scheme_codes is None:
        schemes = list(INSURANCE_SCHEMES.values())
    else:
        schemes = [INSURANCE_SCHEMES[code] for code in scheme_codes if code in INSURANCE_SCHEMES]

    return sorted(schemes, key=lambda s: s['priority'])


def validate_scheme_codes(scheme_codes):
    """
    Validate that all scheme codes are valid

    Args:
        scheme_codes (list): List of scheme codes to validate

    Returns:
        tuple: (valid_codes, invalid_codes)
    """
    valid = []
    invalid = []

    for code in scheme_codes:
        if code in INSURANCE_SCHEMES:
            valid.append(code)
        else:
            invalid.append(code)

    return valid, invalid


def get_scheme_validation_url(scheme_code, month, year, base_url='https://eclaim.nhso.go.th'):
    """
    Generate validation URL for a specific scheme

    Args:
        scheme_code (str): Insurance scheme code
        month (int): Month (1-12)
        year (int): Year in Buddhist Era
        base_url (str): Base URL of NHSO system

    Returns:
        str: Full validation URL
    """
    return (
        f'{base_url}/webComponent/validation/ValidationMainAction.do?'
        f'mo={month}&ye={year}&maininscl={scheme_code}'
    )
