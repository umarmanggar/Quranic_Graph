import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import re

from db import graph_connection, run_batch, sqlite_rows

DIGIT_ONLY = re.compile(r"^[\u0660-\u0669\s]+$")
VERSE_NUMBER = re.compile(r"^\(\d+\)$")

CREATE_WORD = """
UNWIND $rows AS row
MATCH (a:Ayah {verse_key: row.verse_key})
CREATE (a)<-[:OCCURS_IN]-(:WordOccurrence {
  location: row.location,
  position_in_ayah: row.position,
  surface_form: row.surface_form,
  makna_id: row.makna_id,
  transliteration: row.transliteration,
  stem: row.stem
})
"""

LINK_ROOT = """
UNWIND $rows AS row
MATCH (w:WordOccurrence {location: row.location})
MATCH (r:Root {root_id: row.root_id})
CREATE (w)-[:HAS_ROOT]->(r)
"""

LINK_LEMMA = """
UNWIND $rows AS row
MATCH (w:WordOccurrence {location: row.location})
MATCH (l:Lemma {lemma_id: row.lemma_id})
CREATE (w)-[:HAS_LEMMA]->(l)
"""


def word_map(filename, table, drop_verse_number=False):
    result = {}
    for r in sqlite_rows(filename, f"SELECT surah_number, ayah_number, word_number, text FROM {table}"):
        text = r["text"]
        if drop_verse_number and VERSE_NUMBER.match(text or ""):
            continue
        result[(r["surah_number"], r["ayah_number"], int(r["word_number"]))] = text
    return result


def location_map(filename, table, value_col):
    return {
        r["word_location"]: r[value_col]
        for r in sqlite_rows(filename, f"SELECT {value_col}, word_location FROM {table}")
    }


def stem_map():
    texts = {r["id"]: r["text"] for r in sqlite_rows("al-quran/word-stem.db", "SELECT id, text FROM stems")}
    return {
        r["word_location"]: texts.get(r["stem_id"])
        for r in sqlite_rows("al-quran/word-stem.db", "SELECT stem_id, word_location FROM stem_words")
    }


def main():
    makna = word_map("al-quran/indonesian-word-by-word-translation.db", "word_translation", drop_verse_number=True)
    translit = word_map("al-quran/english-wbw-transliteration.db", "word_transliteration")
    stem = stem_map()
    root_of = location_map("al-quran/word-root.db", "root_words", "root_id")
    lemma_of = location_map("al-quran/word-lemma.db", "lemma_words", "lemma_id")

    words, root_links, lemma_links = [], [], []
    for r in sqlite_rows("al-quran/uthmani.db", "SELECT location, surah, ayah, word, text FROM words"):
        if DIGIT_ONLY.match(r["text"] or ""):
            continue
        key = (r["surah"], r["ayah"], r["word"])
        loc = r["location"]
        words.append({
            "location": loc,
            "verse_key": f'{r["surah"]}:{r["ayah"]}',
            "position": r["word"],
            "surface_form": r["text"],
            "makna_id": makna.get(key),
            "transliteration": translit.get(key),
            "stem": stem.get(loc),
        })
        if loc in root_of:
            root_links.append({"location": loc, "root_id": root_of[loc]})
        if loc in lemma_of:
            lemma_links.append({"location": loc, "lemma_id": lemma_of[loc]})

    with graph_connection() as conn:
        run_batch(conn, CREATE_WORD, words)
        run_batch(conn, LINK_ROOT, root_links)
        run_batch(conn, LINK_LEMMA, lemma_links)

    print(f"WordOccurrence: {len(words)} nodes + OCCURS_IN")
    print(f"HAS_ROOT: {len(root_links)} edges, HAS_LEMMA: {len(lemma_links)} edges")


if __name__ == "__main__":
    main()