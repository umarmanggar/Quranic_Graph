import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import graph_connection, run_batch, sqlite_rows

CREATE_ROOT = """
UNWIND $rows AS row
CREATE (:Root {
  root_id: row.root_id,
  arabic_trilateral: row.arabic_trilateral,
  english_trilateral: row.english_trilateral
})
"""

CREATE_LEMMA = """
UNWIND $rows AS row
CREATE (:Lemma {lemma_id: row.lemma_id, text: row.text})
"""


def main():
    roots = [{
        "root_id": r["id"],
        "arabic_trilateral": r["arabic_trilateral"],
        "english_trilateral": r["english_trilateral"],
    } for r in sqlite_rows("al-quran/word-root.db", "SELECT id, arabic_trilateral, english_trilateral FROM roots")]

    lemmas = [{
        "lemma_id": r["id"],
        "text": r["text"],
    } for r in sqlite_rows("al-quran/word-lemma.db", "SELECT id, text FROM lemmas")]

    with graph_connection() as conn:
        run_batch(conn, CREATE_ROOT, roots)
        run_batch(conn, CREATE_LEMMA, lemmas)
    print(f"Root: {len(roots)} nodes, Lemma: {len(lemmas)} nodes")


if __name__ == "__main__":
    main()