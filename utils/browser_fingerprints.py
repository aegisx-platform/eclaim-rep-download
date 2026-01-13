"""
Browser Fingerprints for Parallel Downloads

This module provides different browser fingerprints to simulate
multiple users/browsers when downloading from NHSO e-claim system.
"""

import random
import requests
from typing import Dict, Optional

# Browser fingerprints - simulate different browsers/platforms
BROWSER_FINGERPRINTS = [
    # Chrome on Windows
    {
        'name': 'Chrome/Windows',
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'accept_language': 'th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7',
        'accept_encoding': 'gzip, deflate, br',
        'sec_ch_ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec_ch_ua_mobile': '?0',
        'sec_ch_ua_platform': '"Windows"',
    },
    # Chrome on Mac
    {
        'name': 'Chrome/Mac',
        'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'accept_language': 'th,en-US;q=0.9,en;q=0.8',
        'accept_encoding': 'gzip, deflate, br',
        'sec_ch_ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec_ch_ua_mobile': '?0',
        'sec_ch_ua_platform': '"macOS"',
    },
    # Safari on Mac
    {
        'name': 'Safari/Mac',
        'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'accept_language': 'th-TH,th;q=0.9',
        'accept_encoding': 'gzip, deflate, br',
    },
    # Firefox on Windows
    {
        'name': 'Firefox/Windows',
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'accept_language': 'th,en-US;q=0.7,en;q=0.3',
        'accept_encoding': 'gzip, deflate, br',
    },
    # Firefox on Linux
    {
        'name': 'Firefox/Linux',
        'user_agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'accept_language': 'en-US,en;q=0.8,th;q=0.6',
        'accept_encoding': 'gzip, deflate, br',
    },
    # Edge on Windows
    {
        'name': 'Edge/Windows',
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'accept_language': 'th,en;q=0.9,en-US;q=0.8',
        'accept_encoding': 'gzip, deflate, br',
        'sec_ch_ua': '"Not_A Brand";v="8", "Chromium";v="120", "Microsoft Edge";v="120"',
        'sec_ch_ua_mobile': '?0',
        'sec_ch_ua_platform': '"Windows"',
    },
    # Chrome on Linux
    {
        'name': 'Chrome/Linux',
        'user_agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'accept_language': 'en-US,en;q=0.9,th;q=0.8',
        'accept_encoding': 'gzip, deflate, br',
        'sec_ch_ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec_ch_ua_mobile': '?0',
        'sec_ch_ua_platform': '"Linux"',
    },
    # Safari on iPhone
    {
        'name': 'Safari/iPhone',
        'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'accept_language': 'th-TH,th;q=0.9',
        'accept_encoding': 'gzip, deflate, br',
    },
    # Chrome on Android
    {
        'name': 'Chrome/Android',
        'user_agent': 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'accept_language': 'th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7',
        'accept_encoding': 'gzip, deflate, br',
        'sec_ch_ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec_ch_ua_mobile': '?1',
        'sec_ch_ua_platform': '"Android"',
    },
    # Opera on Windows
    {
        'name': 'Opera/Windows',
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'accept_language': 'th,en-US;q=0.9,en;q=0.8',
        'accept_encoding': 'gzip, deflate, br',
    },
]


def get_fingerprint(index: int) -> Dict:
    """Get a specific fingerprint by index (wraps around if out of range)"""
    return BROWSER_FINGERPRINTS[index % len(BROWSER_FINGERPRINTS)]


def get_random_fingerprint() -> Dict:
    """Get a random browser fingerprint"""
    return random.choice(BROWSER_FINGERPRINTS)


def get_fingerprints_for_workers(num_workers: int) -> list:
    """Get unique fingerprints for specified number of workers"""
    # Shuffle and return first N fingerprints
    shuffled = BROWSER_FINGERPRINTS.copy()
    random.shuffle(shuffled)
    return shuffled[:num_workers]


def create_session_with_fingerprint(fingerprint: Dict) -> requests.Session:
    """Create a requests session with the specified fingerprint"""
    session = requests.Session()

    # Set base headers
    headers = {
        'User-Agent': fingerprint['user_agent'],
        'Accept': fingerprint['accept'],
        'Accept-Language': fingerprint['accept_language'],
        'Accept-Encoding': fingerprint['accept_encoding'],
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

    # Add Chrome-specific headers if present
    if 'sec_ch_ua' in fingerprint:
        headers['Sec-CH-UA'] = fingerprint['sec_ch_ua']
    if 'sec_ch_ua_mobile' in fingerprint:
        headers['Sec-CH-UA-Mobile'] = fingerprint['sec_ch_ua_mobile']
    if 'sec_ch_ua_platform' in fingerprint:
        headers['Sec-CH-UA-Platform'] = fingerprint['sec_ch_ua_platform']

    session.headers.update(headers)

    return session


def create_session_pool(num_sessions: int) -> list:
    """Create a pool of sessions with different fingerprints"""
    fingerprints = get_fingerprints_for_workers(num_sessions)
    sessions = []

    for fp in fingerprints:
        session = create_session_with_fingerprint(fp)
        sessions.append({
            'session': session,
            'fingerprint': fp,
            'name': fp['name'],
            'error_count': 0,
            'last_request_time': 0,
            'total_downloads': 0,
        })

    return sessions


def rotate_session(session_info: Dict) -> Dict:
    """Create a new session with a different fingerprint when current one fails"""
    # Get a new random fingerprint different from current
    current_name = session_info['fingerprint']['name']
    available = [fp for fp in BROWSER_FINGERPRINTS if fp['name'] != current_name]

    if not available:
        available = BROWSER_FINGERPRINTS

    new_fingerprint = random.choice(available)
    new_session = create_session_with_fingerprint(new_fingerprint)

    return {
        'session': new_session,
        'fingerprint': new_fingerprint,
        'name': new_fingerprint['name'],
        'error_count': 0,
        'last_request_time': 0,
        'total_downloads': session_info.get('total_downloads', 0),
    }
