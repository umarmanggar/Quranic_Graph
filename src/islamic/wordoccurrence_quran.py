"""
Migrasi WordOccurrence (quran) -> islamic_kg. Rename position_in_ayah -> position,
edge tetap (WordOccurrence)-[:OCCURS_IN]->(Ayah) (arah sudah konsisten dgn
konvensi terpilih). HAS_ROOT langsung word->root TIDAK dibawa (root sekarang
cuma lewat Lemma, lihat lemma_root.py) -- root tetap reachable transitif lewat
HAS_LEMMA->Lemma->HAS_ROOT->Root.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import graph_connection, run_batch, cypher_rows
import remap

CREATE_WORD = """
UNWIND $rows AS row
MATCH (a:Ayah {verse_key: row.parent_key})
CREATE (a)<-[:OCCURS_IN]-(:WordOccurrence {
  location: row.location, position: row.position, surface_form: row.surface_form,
  makna_id: row.makna_id, transliteration: row.transliteration, stem: row.stem,
  source: row.source
})
"""

LINK_LEMMA = """
UNWIND $rows AS row
MATCH (w:WordOccurrence {location: row.location})
MATCH (l:Lemma {lemma_id: row.lemma_id})
CREATE (w)-[:HAS_LEMMA {rank: row.rank, frequency: row.frequency}]->(l)
"""


def main():
    with graph_connection() as conn:
        words_raw = cypher_rows(conn, "quran_kg",
            "MATCH (w:WordOccurrence)-[:OCCURS_IN]->(a:Ayah) "
            "RETURN w.location, w.position_in_ayah, w.surface_form, w.makna_id, w.transliteration, w.stem, a.verse_key",
            ["location", "position_in_ayah", "surface_form", "makna_id", "transliteration", "stem", "verse_key"],
            desc="WordOccurrence (quran)")

        words = [{
            "location": r["location"], "position": r["position_in_ayah"], "surface_form": r["surface_form"],
            "makna_id": r["makna_id"], "transliteration": r["transliteration"], "stem": r["stem"],
            "parent_key": r["verse_key"], "source": "quran",
        } for r in words_raw]

        quran_lemma_id_to_new = remap.old_lemma_id_to_new(
            conn, "quran_kg", "MATCH (l:Lemma) RETURN l.lemma_id, l.text", ["lemma_id", "text"],
            "lemma_id", "text")

        lemma_links_raw = cypher_rows(conn, "quran_kg",
            "MATCH (w:WordOccurrence)-[:HAS_LEMMA]->(l:Lemma) RETURN w.location, l.lemma_id",
            ["location", "lemma_id"], desc="WordOccurrence-HAS_LEMMA (quran)")
        lemma_links = [{
            "location": r["location"], "lemma_id": quran_lemma_id_to_new[r["lemma_id"]],
            "rank": 1, "frequency": None,
        } for r in lemma_links_raw]

        print("  menulis WordOccurrence (quran)...", flush=True)
        run_batch(conn, CREATE_WORD, words)
        print("  menulis HAS_LEMMA (quran)...", flush=True)
        run_batch(conn, LINK_LEMMA, lemma_links)

    print(f"WordOccurrence (quran): {len(words)} nodes + OCCURS_IN, HAS_LEMMA: {len(lemma_links)} edges")


if __name__ == "__main__":
    main()
