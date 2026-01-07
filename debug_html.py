#!/usr/bin/env python3
"""Debug script to check HTML structure and hrefs"""

import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import re

load_dotenv()

username = os.getenv('ECLAIM_USERNAME')
password = os.getenv('ECLAIM_PASSWORD')

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
})

# Login
login_url = 'https://eclaim.nhso.go.th/webComponent/login/LoginAction.do'
print("Logging in...")
session.post(login_url, data={'user': username, 'pass': password}, timeout=120)

# Get validation page
validation_url = 'https://eclaim.nhso.go.th/webComponent/validation/ValidationMainAction.do?maininscl=ucs'
print("Fetching validation page...")
response = session.get(validation_url, timeout=120)

# Parse HTML
soup = BeautifulSoup(response.content, 'lxml')

# Find download excel links
excel_links = soup.find_all('a', string=re.compile(r'download excel', re.IGNORECASE))

print(f"\nFound {len(excel_links)} download excel links\n")

for i, link in enumerate(excel_links[:5], 1):  # Show first 5
    href = link.get('href')
    print(f"Link {i}:")
    print(f"  href: {href}")
    print(f"  href type: {type(href)}")
    print()
