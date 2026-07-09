import setup, surah, ayah, root_lemma, wordoccurrence, translation, verify

STEPS = [setup, surah, ayah, root_lemma, wordoccurrence, translation, verify]

def main():
    for step in STEPS:
        print(f"\n=== {step.__name__} ===")
        step.main()

if __name__ == "__main__":
    main()