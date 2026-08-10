"""
Orkestrator pipeline fatwa. Prasyarat: src/islamic/main.py sudah pernah
dijalankan (islamic_kg harus sudah punya Hadith & Ayah node -- ditegakkan
lewat fail-fast guard di setup.py).

python main.py
"""
import setup
import fatwa
import fatwa_hadith
import fatwa_quran
import verify

STEPS = [setup, fatwa, fatwa_hadith, fatwa_quran, verify]


def main():
    for step in STEPS:
        print(f"\n=== {step.__name__} ===", flush=True)
        step.main()


if __name__ == "__main__":
    main()
