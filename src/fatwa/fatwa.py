"""
Node Fatwa, satu per fatwa terdeteksi (lihat segmentation.py utk logika
segmentasi). Tidak ada edge di sini -- RELATED_HADITH/RELATED_QURAN dibuat
di fatwa_hadith.py/fatwa_quran.py setelah node Fatwa ini ada.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import graph_connection, run_batch
from segmentation import segment_all_books, BOOK_IDS

CREATE_FATWA = """
UNWIND $rows AS row
CREATE (:Fatwa {
  fatwa_id: row.fatwa_id, book: row.book, fatwa_number: row.fatwa_number,
  text_arabic: row.text_arabic, n_footnotes: row.n_footnotes
})
"""


def build_rows():
    records = segment_all_books()
    return [
        {
            "fatwa_id": r["fatwa_id"], "book": r["book"], "fatwa_number": r["fatwa_number"],
            "text_arabic": r["text_arabic"], "n_footnotes": r["n_footnotes"],
        }
        for r in records
    ]


def main():
    rows = build_rows()
    with graph_connection() as conn:
        run_batch(conn, CREATE_FATWA, rows)

    print(f"Fatwa: {len(rows)} node dibuat")
    for book_id in BOOK_IDS:
        n = sum(1 for r in rows if r["book"] == book_id)
        n_fn = sum(1 for r in rows if r["book"] == book_id and r["n_footnotes"] > 0)
        print(f"  {book_id:24} {n:5} fatwa, {n_fn:5} dgn >=1 footnote")


if __name__ == "__main__":
    main()
