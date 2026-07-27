"""
Copy 1:1 Surah, Ayah, Translation dari quran_kg ke islamic_kg. Tidak ada
redudansi/dedup di sini -- ketiganya cuma ada di quran_kg, jadi murni salin
node + edge PART_OF/HAS_TRANSLATION apa adanya.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import graph_connection, run_batch, cypher_rows

CREATE_SURAH = """
UNWIND $rows AS row
CREATE (:Surah {
  surah_id: row.surah_id, name_arabic: row.name_arabic, name_latin: row.name_latin,
  revelation_place: row.revelation_place, total_ayah: row.total_ayah
})
"""

CREATE_AYAH = """
UNWIND $rows AS row
CREATE (:Ayah {
  verse_key: row.verse_key, surah_id: row.surah_id, ayah_number: row.ayah_number,
  text_arabic: row.text_arabic, juz: row.juz, words_count: row.words_count
})
"""

LINK_AYAH_SURAH = """
UNWIND $rows AS row
MATCH (a:Ayah {verse_key: row.verse_key})
MATCH (s:Surah {surah_id: row.surah_id})
CREATE (a)-[:PART_OF]->(s)
"""

CREATE_TRANSLATION = """
UNWIND $rows AS row
MATCH (a:Ayah {verse_key: row.verse_key})
CREATE (a)-[:HAS_TRANSLATION]->(:Translation {language: row.language, source: row.source, text: row.text})
"""


def main():
    with graph_connection() as conn:
        surahs = cypher_rows(conn, "quran_kg",
            "MATCH (s:Surah) RETURN s.surah_id, s.name_arabic, s.name_latin, s.revelation_place, s.total_ayah",
            ["surah_id", "name_arabic", "name_latin", "revelation_place", "total_ayah"], desc="Surah")

        ayat = cypher_rows(conn, "quran_kg",
            "MATCH (a:Ayah) RETURN a.verse_key, a.surah_id, a.ayah_number, a.text_arabic, a.juz, a.words_count",
            ["verse_key", "surah_id", "ayah_number", "text_arabic", "juz", "words_count"], desc="Ayah")

        translations = cypher_rows(conn, "quran_kg",
            "MATCH (a:Ayah)-[:HAS_TRANSLATION]->(t:Translation) "
            "RETURN a.verse_key, t.language, t.source, t.text",
            ["verse_key", "language", "source", "text"], desc="Translation")

        print("  menulis Surah...", flush=True)
        run_batch(conn, CREATE_SURAH, surahs)
        print("  menulis Ayah + PART_OF...", flush=True)
        run_batch(conn, CREATE_AYAH, ayat)
        run_batch(conn, LINK_AYAH_SURAH, [{"verse_key": r["verse_key"], "surah_id": r["surah_id"]} for r in ayat])
        print("  menulis Translation...", flush=True)
        run_batch(conn, CREATE_TRANSLATION, translations)

    print(f"Surah: {len(surahs)} nodes, Ayah: {len(ayat)} nodes + PART_OF, Translation: {len(translations)} nodes + HAS_TRANSLATION")


if __name__ == "__main__":
    main()
