"""
Orkestrator islamic_kg. Gabungkan quran_kg + hadith_kg (baca-saja, tidak
mengubah keduanya) jadi graph baru islamic_kg. Urutan wajib: node induk dulu
(surah/ayah, koleksi/bab/hadith, book/tafsir), lalu Lemma/Root unifikasi,
baru WordOccurrence per domain (butuh parent + Lemma sudah ada).

python main.py
"""
import time
import datetime

import setup
import surah_ayah
import koleksi_bab_hadith
import book_tafsir
import hadith_tafsir
import lemma_root
import wordoccurrence_quran
import wordoccurrence_tafsir
import wordoccurrence_hadith
import verify

STEPS = [
    setup, surah_ayah, koleksi_bab_hadith, book_tafsir, hadith_tafsir, lemma_root,
    wordoccurrence_quran, wordoccurrence_tafsir, wordoccurrence_hadith, verify,
]


def main():
    pipeline_start = time.time()
    for step in STEPS:
        now = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"\n=== {step.__name__} ({now}) ===", flush=True)
        step_start = time.time()
        step.main()
        print(f"--- {step.__name__} selesai dalam {time.time() - step_start:.1f}s ---", flush=True)
    print(f"\n=== pipeline selesai total {time.time() - pipeline_start:.1f}s ===", flush=True)


if __name__ == "__main__":
    main()
