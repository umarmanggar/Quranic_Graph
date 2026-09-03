"""
Orkestrator pipeline similarity (edge :isSimilar). Prasyarat: src/islamic/main.py
dan src/fatwa/main.py sudah dijalankan (islamic_kg harus punya node Ayah/Hadith/
Tafsir/Fatwa -- ditegakkan lewat guard di setup.py). Butuh env OPENAI_API_KEY.

    python main.py

calibrate.py SENGAJA di luar STEPS -- jalankan manual di antara index_search dan
edges untuk menetapkan config.THRESHOLD:

    python index_search.py && python calibrate.py   # tinjau CSV, setel THRESHOLD
    python edges.py && python verify.py
"""
import time
import datetime

import setup
import fetch
import chunk
import embed
import index_search
import edges
import verify

STEPS = [setup, fetch, chunk, embed, index_search, edges, verify]


def main():
    t0 = time.time()
    for step in STEPS:
        now = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"\n=== {step.__name__} ({now}) ===", flush=True)
        s = time.time()
        step.main()
        print(f"--- {step.__name__} selesai dalam {time.time() - s:.1f}s ---", flush=True)
    print(f"\n=== pipeline selesai total {time.time() - t0:.1f}s ===", flush=True)


if __name__ == "__main__":
    main()
