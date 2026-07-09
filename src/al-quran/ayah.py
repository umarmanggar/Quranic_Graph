import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json

from db import graph_connection, run_batch, sqlite_rows

CREATE_AYAH = """
UNWIND $rows AS row
CREATE (:Ayah {
  verse_key: row.verse_key,
  surah_id: row.surah_id,
  ayah_number: row.ayah_number,
  text_arabic: row.text_arabic,
  juz: row.juz,
  words_count: row.words_count
})
"""

LINK_SURAH = """
UNWIND $rows AS row
MATCH (a:Ayah {verse_key: row.verse_key})
MATCH (s:Surah {surah_id: row.surah_id})
CREATE (a)-[:PART_OF]->(s)
"""


def build_juz_map():
    mapping = {}
    for r in sqlite_rows("al-quran/quran-metadata-juz.sqlite", "SELECT juz_number, verse_mapping FROM juz"):
        for surah, rng in json.loads(r["verse_mapping"]).items():
            start, end = rng.split("-") if "-" in rng else (rng, rng)
            for ayah in range(int(start), int(end) + 1):
                mapping[(int(surah), ayah)] = r["juz_number"]
    return mapping


def strip_verse_number(text):
    return "".join(c for c in text if not ("\u0660" <= c <= "\u0669")).strip()


def main():
    juz = build_juz_map()
    src = sqlite_rows(
        "al-quran/quran-metadata-ayah.sqlite",
        "SELECT surah_number, ayah_number, verse_key, words_count, text FROM verses",
    )
    rows = [{
        "verse_key": r["verse_key"],
        "surah_id": r["surah_number"],
        "ayah_number": r["ayah_number"],
        "text_arabic": strip_verse_number(r["text"]),
        "juz": juz.get((r["surah_number"], r["ayah_number"])),
        "words_count": r["words_count"],
    } for r in src]

    with graph_connection() as conn:
        run_batch(conn, CREATE_AYAH, rows)
        run_batch(conn, LINK_SURAH, [
            {"verse_key": r["verse_key"], "surah_id": r["surah_id"]} for r in rows
        ])
    print(f"Ayah: {len(rows)} nodes + PART_OF edges")


if __name__ == "__main__":
    main()