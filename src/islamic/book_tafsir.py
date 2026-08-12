"""
Copy 1:1 Book, Tafsir dari quran_kg ke islamic_kg. Tidak ada redudansi/dedup
di sini -- keduanya cuma ada di quran_kg. INTERPRETS di-MATCH ulang ke Ayah
milik islamic_kg sendiri (surah_ayah.py harus sudah jalan duluan).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import graph_connection, run_batch, cypher_rows

CREATE_BOOK = """
UNWIND $rows AS row
CREATE (:Book {book_id: row.book_id, title: row.title})
"""

CREATE_TAFSIR = """
UNWIND $rows AS row
MATCH (b:Book {book_id: row.book_id})
CREATE (b)<-[:PART_OF_BOOK]-(:Tafsir {
  tafsir_id: row.tafsir_id, book_id: row.book_id,
  text_arabic: row.text_arabic, text_indonesia: row.text_indonesia, text_english: row.text_english
})
"""

LINK_INTERPRETS = """
UNWIND $rows AS row
MATCH (t:Tafsir {tafsir_id: row.tafsir_id})
MATCH (a:Ayah {verse_key: row.verse_key})
CREATE (t)-[:INTERPRETS]->(a)
"""


def main():
    with graph_connection() as conn:
        tafsirs = cypher_rows(conn, "quran_kg",
            "MATCH (t:Tafsir {book_id:'tafsir_ibnu_katsir'})-[:PART_OF_BOOK]->(b:Book) "
            "RETURN t.tafsir_id, t.text_arabic, t.text_indonesia, t.text_english, b.book_id",
            ["tafsir_id", "text_arabic", "text_indonesia", "text_english", "book_id"], desc="Tafsir")

        interprets = cypher_rows(conn, "quran_kg",
            "MATCH (t:Tafsir {book_id:'tafsir_ibnu_katsir'})-[:INTERPRETS]->(a:Ayah) RETURN t.tafsir_id, a.verse_key",
            ["tafsir_id", "verse_key"], desc="INTERPRETS")

        print("  menulis Tafsir + PART_OF_BOOK...", flush=True)
        run_batch(conn, CREATE_TAFSIR, tafsirs)
        print("  menulis INTERPRETS...", flush=True)
        run_batch(conn, LINK_INTERPRETS, interprets)

    print(f"Tafsir: {len(tafsirs)} nodes + PART_OF_BOOK, INTERPRETS: {len(interprets)} edges")


if __name__ == "__main__":
    main()