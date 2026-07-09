"""Cek jumlah halaman & total hadis tiap tema di Hadits Tazkia.

Sekaligus menguji apakah `requests` bisa menembus Cloudflare (tanpa Selenium).
Kalau berhasil, scraper tema/kedudukan bisa dipindah dari Selenium ke requests
-> jauh lebih cepat.

Catatan: total di sini mencakup 14 koleksi, BUKAN hanya Kutubus Sittah.
"""

import re
import time

import requests
from bs4 import BeautifulSoup

BASE = "https://hadits.tazkia.ac.id"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}
PAGE_RE = re.compile(r"page_haditses=(\d+)")


def get_soup(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def last_page(soup):
    nums = [
        int(m.group(1))
        for a in soup.select("a.page-link")
        if (m := PAGE_RE.search(a.get("href", "")))
    ]
    return max(nums) if nums else 1


def info(kind, idx):
    soup = get_soup(f"{BASE}/hadits/{kind}/{idx}?page_haditses=1")
    name = soup.select_one("h1")
    last = last_page(soup)

    soup_last = get_soup(f"{BASE}/hadits/{kind}/{idx}?page_haditses={last}")
    on_last = len(soup_last.select("div.hadits"))
    per_page = len(soup.select("div.hadits")) or 10
    total = (last - 1) * per_page + on_last
    return (name.get_text(strip=True) if name else f"{kind} {idx}"), last, total


def main():
    grand = 0
    for i in range(1, 15):
        try:
            name, last, total = info("tema", i)
        except Exception as e:
            print(f"{i:2}. GAGAL: {type(e).__name__}")
            continue
        grand += total
        print(f"{i:2}. {name:<30} halaman={last:<5} total={total}")
        time.sleep(0.5)

    print(f"\njumlah semua pasangan tema (14 koleksi): {grand}")
    print("catatan: ini bukan jumlah hadis unik, dan bukan hanya Kutubus Sittah")


if __name__ == "__main__":
    main()
