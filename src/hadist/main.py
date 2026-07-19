"""
Orkestrator tahap 2. Jalankan SETELAH lemmatize.py (tahap 1) menghasilkan
hadith_analyzed.db. Urutan: setup -> root_lemma -> structure -> words -> verify.
Node dulu semua, edge nyusul di tiap modul (butuh node target sudah ada).

python main.py
"""
import setup, root_lemma, structure, words, verify

STEPS = [setup, root_lemma, structure, words, verify]


def main():
    for step in STEPS:
        print(f"\n=== {step.__name__} ===")
        step.main()


if __name__ == "__main__":
    main()
