import sys

import setup, book, commentary, wordoccurrence, verify
from books import BOOKS

STEPS = [setup, book, commentary, wordoccurrence]


def main():
    args = sys.argv[1:]
    if not args:
        print("usage: python main.py <book_id> [book_id ...]")
        print("available:", ", ".join(BOOKS))
        return

    unknown = [a for a in args if a not in BOOKS]
    if unknown:
        raise SystemExit(f"unknown book_id: {unknown}")

    for book_id in args:
        print(f"\n########## {book_id} ##########")
        for step in STEPS:
            print(f"\n=== {step.__name__} ===")
            step.main(book_id)

    print("\n=== verify ===")
    verify.main()


if __name__ == "__main__":
    main()