"""Scrape Kutubus Sittah dari Hadits Tazkia (hadits.tazkia.ac.id).

Hierarki: Koleksi -> Bab -> Matan. URL bab: /hadits/kitab/{koleksi}:{bab}.
Teks Arab diambil utuh (sanad + matan menyatu); pemisahan dilakukan saat
pengolahan, bukan saat scrape. Grade kondisional: ada di 4 Sunan, kosong di
Bukhari & Muslim (normal). Baris yang gagal validasi dikarantina, tidak
ditulis diam-diam ke data utama. Tahan-putus lewat progress.txt; jalankan
ulang untuk melanjutkan.

Uji BOOK_IDS=[1] dulu (grade kosong), lalu [3] (grade terisi), baru [1..6].
Selector tak terverifikasi ditandai "# CEK INI".
"""

import csv
import os
import re
import time
from dataclasses import dataclass, asdict, fields
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

BOOK_IDS = [1, 2, 3, 4, 5, 6]
BASE = "https://hadits.tazkia.ac.id"
WAIT = 15
POLITE_DELAY = 0.7
HEADLESS = False

DATA_DIR = Path(r"D:\INTERNSHIP\QURANIC\data\hadist\scrap")
OUTFILE = DATA_DIR / "kutubus_sittah.csv"
KARANTINA_FILE = DATA_DIR / "karantina.csv"
PROGRESS_FILE = DATA_DIR / "progress.txt"

KOLEKSI_NAMES = {
    1: "Shahih Bukhari",
    2: "Shahih Muslim",
    3: "Sunan Tirmidzi",
    4: "Sunan Abu Dawud",
    5: "Sunan Nasa'i",
    6: "Sunan Ibnu Majah",
}

_REF = re.compile(r'^[^\d\n]{0,28}\d+\s*:\s*')
_ARABIC = re.compile(r'[\u0600-\u06FF]')
_LATIN = re.compile(r'[A-Za-z]')


@dataclass(frozen=True)
class Hadith:
    hadith_id: str
    koleksi_id: int
    bab_no: int
    koleksi: str
    bab_ar: str
    bab_id: str
    arabic_full: str
    terjemah_id: str
    grade: str


FIELDS = [f.name for f in fields(Hadith)]


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


def load_seen_ids():
    if not OUTFILE.exists():
        return set()
    with open(OUTFILE, encoding="utf-8-sig", newline="") as f:
        return {row["hadith_id"] for row in csv.DictReader(f)}


def _append(path, rows, fieldnames):
    new = not os.path.exists(path)
    enc = "utf-8-sig" if new else "utf-8"
    with open(path, "a", encoding=enc, newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if new:
            w.writeheader()
        for r in rows:
            w.writerow(r)


def append_rows(hadiths):
    _append(OUTFILE, [asdict(h) for h in hadiths], FIELDS)


def append_karantina(pairs):
    rows = [{**asdict(h), "reason": reason} for h, reason in pairs]
    _append(KARANTINA_FILE, rows, FIELDS + ["reason"])


def mark_done(key):
    with open(PROGRESS_FILE, "a", encoding="utf-8") as f:
        f.write(key + "\n")


def get_babs(driver, book_id):
    safe_get(driver, f"{BASE}/kitab/{book_id}")
    card_sel = "div.card[id^='kitab']"
    WebDriverWait(driver, WAIT).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, card_sel))
    )

    babs = []
    for card in driver.find_elements(By.CSS_SELECTOR, card_sel):
        try:
            bab_no = int(card.get_attribute("id").replace("kitab", ""))
        except (ValueError, AttributeError):
            continue
        try:
            bab_id = card.find_element(
                By.CSS_SELECTOR, "a.text-id"
            ).get_attribute("textContent").strip()
        except NoSuchElementException:
            bab_id = ""
        try:
            bab_ar = card.find_element(
                By.CSS_SELECTOR, ".text-ar"  # CEK INI
            ).get_attribute("textContent").strip()
        except NoSuchElementException:
            bab_ar = ""
        babs.append((bab_no, bab_id, bab_ar))

    babs.sort(key=lambda x: x[0])
    return babs


def extract_grade(elm):
    try:
        label = elm.find_element(
            By.XPATH, ".//*[normalize-space(text())='Grade']"  # CEK INI
        )
        text = label.find_element(By.XPATH, "..").text.strip()
    except (NoSuchElementException, StaleElementReferenceException):
        return ""
    return re.sub(r'^\s*Grade\s*', '', text).strip()


def extract_one(elm, book_id, bab_no, koleksi, bab_id, bab_ar):
    def safe(xpath):
        try:
            return elm.find_element(By.XPATH, xpath).text.strip()
        except (NoSuchElementException, StaleElementReferenceException):
            return ""

    return Hadith(
        hadith_id=safe(".//h2"),
        koleksi_id=book_id,
        bab_no=bab_no,
        koleksi=koleksi,
        bab_ar=bab_ar,
        bab_id=bab_id,
        arabic_full=_REF.sub('', safe(".//p[1]"), count=1).strip(),
        terjemah_id=_REF.sub('', safe(".//p[2]"), count=1).strip(),
        grade=extract_grade(elm),
    )


def scrape_bab(driver, book_id, bab_no, koleksi, bab_id, bab_ar, seen_ids):
    base_url = f"{BASE}/hadits/kitab/{book_id}:{bab_no}"
    rows = []
    page = 1

    while True:
        safe_get(driver, f"{base_url}?page_haditses={page}")
        time.sleep(POLITE_DELAY)

        try:
            WebDriverWait(driver, WAIT).until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "hadits"))
            )
        except TimeoutException:
            break   # halaman kosong = habis

        elms = driver.find_elements(By.CLASS_NAME, "hadits")
        if not elms:
            break

        before = len(rows)
        for elm in elms:
            h = extract_one(elm, book_id, bab_no, koleksi, bab_id, bab_ar)
            if h.hadith_id and h.hadith_id not in seen_ids:
                seen_ids.add(h.hadith_id)
                rows.append(h)

        # tidak ada hadis baru di halaman ini = mentok (mis. halaman diulang)
        if len(rows) == before:
            break

        page += 1

    return rows


def is_valid(h):
    if not _ARABIC.search(h.arabic_full):
        return False, "arabic_full tanpa huruf Arab"
    if not _LATIN.search(h.terjemah_id):
        return False, "terjemah_id tanpa huruf Latin"
    return True, ""


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    done = load_done()
    seen_ids = load_seen_ids()
    print(f"resume: {len(done)} bab selesai, {len(seen_ids)} hadith sudah ada")

    driver = setup_driver()
    try:
        for book_id in BOOK_IDS:
            koleksi = KOLEKSI_NAMES.get(book_id, f"Koleksi {book_id}")
            babs = get_babs(driver, book_id)
            print(f"{koleksi} (koleksi {book_id}): {len(babs)} bab")

            for bab_no, bab_id, bab_ar in babs:
                key = f"{book_id}:{bab_no}"
                if key in done:
                    continue
                try:
                    rows = scrape_bab(
                        driver, book_id, bab_no, koleksi, bab_id, bab_ar, seen_ids
                    )
                except WebDriverException as e:
                    print(f"  ERROR {key} ({bab_id}): {type(e).__name__}, skip")
                    continue

                good, bad = [], []
                for h in rows:
                    ok, reason = is_valid(h)
                    (good if ok else bad).append((h, reason))

                append_rows([h for h, _ in good])
                if bad:
                    append_karantina(bad)
                mark_done(key)
                done.add(key)
                tail = f" (KARANTINA {len(bad)})" if bad else ""
                print(f"  {key} | {bab_id}: +{len(good)}{tail}")
                time.sleep(POLITE_DELAY)
    finally:
        driver.quit()

    print("berhenti. jalankan lagi untuk melanjutkan kalau belum kelar.")


if __name__ == "__main__":
    main()