import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import graph_connection, run_batch

CREATE_BOOK = """
UNWIND $rows AS row
CREATE (:Book {book_id: row.book_id, title: row.title})
"""


def main():
    rows = [{"book_id": "tafsir_as_saadi", "title": "Tafsir As-Sa'di (Taisir al-Karim al-Rahman)"}]
    with graph_connection() as conn:
        run_batch(conn, CREATE_BOOK, rows)
    print(f"Book: {len(rows)} nodes")


if __name__ == "__main__":
    main()
