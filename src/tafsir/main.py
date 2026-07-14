import setup, book, commentary, wordoccurrence, verify

STEPS = [setup, book, commentary, wordoccurrence, verify]

def main():
    for step in STEPS:
        print(f"\n=== {step.__name__} ===")
        step.main()

if __name__ == "__main__":
    main()
