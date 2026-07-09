"""Scrape pemetaan hadis -> kedudukan dari Hadits Tazkia.

Halaman /hadits/kedudukan/{N} (N=1..9) mendaftar hadis LINTAS 14 koleksi. Kita
hanya menyimpan yang termasuk 6 Kutubus Sittah (lihat KOLEKSI_SITTAH); sisanya
dibuang. Output BUKAN hadis lengkap, melainkan pasangan (hadith_id, kedudukan).

hadith_id dinormalkan (buang '#', rapikan spasi) supaya cocok dengan kolom
hadith_id di kutubus_sittah.csv. WAJIB diverifikasi saat uji: bandingkan satu
hadith_id di CSV utama dengan judul di halaman kedudukan.

Paginasi sama dengan scraper bab: ?page_haditses=N sampai kosong. Tahan-putus
per kedudukan lewat progress_kedudukan.txt. Uji KEDUDUKAN_IDS=[1] dulu.
"""

import csv
import os
import re
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)
from webdriver_manager.chrome import ChromeDriverManager

KEDUDUKAN_IDS = [1]                      # uji [1] dulu; lengkap = list(range(1, 10))
BASE = "https://hadits.tazkia.ac.id"
WAIT = 15
POLITE_DELAY = 0.7
HEADLESS = False

DATA_DIR = Path(r"D:\INTERNSHIP\QURANIC\data\hadist\scrap")
OUTFILE = DATA_DIR / "hadith_kedudukan.csv"
PROGRESS_FILE = DATA_DIR / "progress_kedudukan.txt"

# hanya simpan hadis dari koleksi ini (judul <h2> diawali salah satu nama ini)
KOLEKSI_SITTAH = (
    "Shahih Bukhari",
    "Shahih Muslim",
    "Sunan Tirmidzi",
    "Sunan Abu Dawud",
    "Sunan Nasa'i",
    "Sunan Ibnu Majah",
)

FIELDS = ["hadith_id", "kedudukan"]


def setup_driver():
    options = Options()
    if HEADLESS:
        options.add_argument("--headless=new")
    options.page_load_strategy = "eager"
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=options
    )
    driver.set_page_load_timeout(60)
    return driver


def safe_get(driver, url):
    try:
        driver.get(url)
    except TimeoutException:
        try:
            driver.execute_script("window.stop();")
        except WebDriverException:
            pass


def load_done():
    if not PROGRESS_FILE.exists():
        return set()
    with open(PROGRESS_FILE, encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def load_seen_pairs():
    if not OUTFILE.exists():
        return set()
    with open(OUTFILE, encoding="utf-8-sig", newline="") as f:
        return {(r["hadith_id"], r["kedudukan"]) for r in csv.DictReader(f)}


def append_rows(rows):
    new = not OUTFILE.exists()
    enc = "utf-8-sig" if new else "utf-8"
    with open(OUTFILE, "a", encoding=enc, newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for r in rows:
            w.writerow(r)


def mark_done(key):
    with open(PROGRESS_FILE, "a", encoding="utf-8") as f:
        f.write(key + "\n")


def norm_id(text):
    # "Muwatha' Malik #1" -> "Muwatha' Malik 1"; rapikan spasi
    return re.sub(r'\s+', ' ', text.replace('#', '')).strip()


def in_sittah(hadith_id):
    return any(hadith_id.startswith(k) for k in KOLEKSI_SITTAH)


_PAGE_RE = re.compile(r'page_haditses=(\d+)')


def get_kedudukan_name(driver):
    try:
        return driver.find_element(
            By.CSS_SELECTOR, "div.heading h1.text-id"  # CEK INI
        ).text.strip()
    except NoSuchElementException:
        return ""


def get_last_page(driver):
    # Halaman > terakhir tidak dikembalikan kosong (di-clamp ke halaman
    # terakhir), jadi batas berhenti diambil dari navigasi: page_haditses
    # terbesar di antara semua link paginasi (link 'Last' membawa nomor ini).
    nums = []
    for a in driver.find_elements(By.CSS_SELECTOR, "a.page-link"):
        m = _PAGE_RE.search(a.get_attribute("href") or "")
        if m:
            nums.append(int(m.group(1)))
    return max(nums) if nums else 1


def load_page(driver, url):
    """True kalau halaman berhasil memuat blok .hadits. Coba ulang 3x."""
    for attempt in range(3):
        safe_get(driver, url)
        time.sleep(POLITE_DELAY)
        try:
            WebDriverWait(driver, WAIT).until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "hadits"))
            )
            return True
        except TimeoutException:
            if attempt < 2:
                print(f"    retry {url}")
                time.sleep(3)
    return False


def scrape_kedudukan(driver, kedudukan_id, seen_pairs):
    """(rows, nama, completed). completed=False -> jangan tandai selesai."""
    base_url = f"{BASE}/hadits/kedudukan/{kedudukan_id}"
    rows = []
    kedudukan_name = ""
    last_page = None
    page = 1

    while True:
        if not load_page(driver, f"{base_url}?page_haditses={page}"):
            return rows, kedudukan_name, False   # gagal muat -> belum selesai

        if last_page is None:
            last_page = get_last_page(driver)
            kedudukan_name = get_kedudukan_name(driver) or f"kedudukan {kedudukan_id}"

        for elm in driver.find_elements(By.CLASS_NAME, "hadits"):
            try:
                raw = elm.find_element(By.XPATH, ".//h2").text.strip()
            except (NoSuchElementException, StaleElementReferenceException):
                continue
            hadith_id = norm_id(raw)
            if not hadith_id or not in_sittah(hadith_id):
                continue
            pair = (hadith_id, kedudukan_name)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            rows.append({"hadith_id": hadith_id, "kedudukan": kedudukan_name})

        if page >= last_page:
            return rows, kedudukan_name, True
        page += 1


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    done = load_done()
    seen_pairs = load_seen_pairs()
    print(f"resume: {len(done)} kedudukan selesai, {len(seen_pairs)} pasangan ada")

    driver = setup_driver()
    try:
        for kedudukan_id in KEDUDUKAN_IDS:
            key = f"kedudukan:{kedudukan_id}"
            if key in done:
                continue
            try:
                rows, kedudukan_name, completed = scrape_kedudukan(
                    driver, kedudukan_id, seen_pairs
                )
            except WebDriverException as e:
                print(f"  ERROR {key}: {type(e).__name__}, akan diulang")
                continue

            append_rows(rows)
            if completed:
                mark_done(key)
                done.add(key)
                print(f"  {key} ({kedudukan_name}): +{len(rows)} hadis sittah")
            else:
                print(f"  {key} BELUM SELESAI (+{len(rows)}), jalankan ulang")
            time.sleep(POLITE_DELAY)
    finally:
        driver.quit()

    print("berhenti. jalankan lagi untuk melanjutkan kalau belum kelar.")


if __name__ == "__main__":
    main()