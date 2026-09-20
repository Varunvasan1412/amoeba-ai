import requests
import re

r = requests.get('https://newlook.ahattrickz.com/payroll/list', timeout=10)
links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', r.text, re.I)
print(f"Total links: {len(links)}")
for href, text in links:
    clean_text = re.sub(r'<[^>]+>', '', text).strip()
    if not href.startswith('#') and clean_text:
        print(f"  {clean_text:35} -> {href}")




