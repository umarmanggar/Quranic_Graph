import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import graph_connection, run_batch
from books import BOOKS

CREATE_BOOK = """
UNWIND $rows AS row
CREATE (:Book {book_id: row.book_id, title: row.title})
"""


def main(book_id):
    rows = [{"book_id": book_id, "title": BOOKS[book_id]["title"]}]
    with graph_connection() as conn:
        run_batch(conn, CREATE_BOOK, rows)
    print(f"Book: {rows[0]['title']}")