import httpx
import re
from bs4 import BeautifulSoup

url = 'https://ncode.syosetu.com/n4423lw/'
resp = httpx.get(url, headers={'User-Agent': 'Mozilla/5.0'})
print('status', resp.status_code)
soup = BeautifulSoup(resp.text, 'lxml')
for sel in ['.novel_subinfo2', '.novel_subinfo', '.novel_other', '.novel_writername', '.novel_ex']:
    el = soup.select_one(sel)
    if el:
        print(sel, '=>', el.get_text(separator='|', strip=True)[:300])

text = soup.get_text(separator='|', strip=True)
for m in re.finditer(r"\d{4}/\d{2}/\d{2}", text):
    start = max(0, m.start() - 50)
    end = min(len(text), m.end() + 50)
    print('date', m.group(0), 'context:', text[start:end])
