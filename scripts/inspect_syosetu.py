import httpx
from bs4 import BeautifulSoup

url = "https://ncode.syosetu.com/n4423lw/"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

resp = httpx.get(url, headers=headers)
resp.raise_for_status()

soup = BeautifulSoup(resp.text, "lxml")

print("TITLE:", soup.find("p", class_="novel_title"))
print("AUTHOR:", soup.find(id="novel_writername"))

chapter_links = soup.select("dl.novel_sublist2 > dd > a")
print("dl.novel_sublist2 count:", len(chapter_links))
if chapter_links:
    print("first:", chapter_links[0].get('href'), chapter_links[0].get_text(strip=True))

alt_links = soup.select("div#novel_sublist > div > a")
print("div#novel_sublist count:", len(alt_links))
if alt_links:
    print("alt first:", alt_links[0].get('href'), alt_links[0].get_text(strip=True))
