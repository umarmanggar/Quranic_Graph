"""
Migrasi TafsirWordOccurrence -> WordOccurrence (islamic_kg). word_occurrence_id
-> location, position_in_tafsir -> position, edge PART_OF_TAFSIR di-rename jadi
OCCURS_IN (konvensi terpilih: semua WordOccurrence nunjuk ke parent-nya lewat
OCCURS_IN). HAS_TAFSIR_LEMMA -> HAS_LEMMA, lemma_id di-remap ke Lemma unifikasi.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import graph_connection, run_batch, cypher_rows
import remap

CREATE_WORD = """
UNWIND $rows AS row
MATCH (t:Tafsir {tafsir_id: row.parent_key})
CREATE (t)<-[:OCCURS_IN]-(:WordOccurrence {
  location: row.location, position: row.position, surface_form: row.surface_form,
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
            "MATCH (w:TafsirWordOccurrence)-[:PART_OF_TAFSIR]->(t:Tafsir {book_id:'tafsir_ibnu_katsir'}) "
            "RETURN w.word_occurrence_id, w.position_in_tafsir, w.surface_form, t.tafsir_id",
            ["word_occurrence_id", "position_in_tafsir", "surface_form", "tafsir_id"],
            desc="TafsirWordOccurrence")

        words = [{
            "location": r["word_occurrence_id"], "position": r["position_in_tafsir"],
            "surface_form": r["surface_form"], "parent_key": r["tafsir_id"], "source": "tafsir",
        } for r in words_raw]

        tafsir_lemma_id_to_new = remap.old_lemma_id_to_new(
            conn, "quran_kg", "MATCH (l:TafsirLemma) RETURN l.lemma_id, l.text", ["lemma_id", "text"],
            "lemma_id", "text")

        lemma_links_raw = cypher_rows(conn, "quran_kg",
            "MATCH (w:TafsirWordOccurrence)-[:PART_OF_TAFSIR]->(t:Tafsir {book_id:'tafsir_ibnu_katsir'}) "
            "MATCH (w)-[:HAS_TAFSIR_LEMMA]->(l:TafsirLemma) RETURN w.word_occurrence_id, l.lemma_id",
            ["word_occurrence_id", "lemma_id"], desc="TafsirWordOccurrence-HAS_TAFSIR_LEMMA")
        lemma_links = [{
            "location": r["word_occurrence_id"], "lemma_id": tafsir_lemma_id_to_new[r["lemma_id"]],
            "rank": 1, "frequency": None,
        } for r in lemma_links_raw]

        print("  menulis WordOccurrence (tafsir)...", flush=True)
        run_batch(conn, CREATE_WORD, words)
        print("  menulis HAS_LEMMA (tafsir)...", flush=True)
        run_batch(conn, LINK_LEMMA, lemma_links)

    print(f"WordOccurrence (tafsir): {len(words)} nodes + OCCURS_IN, HAS_LEMMA: {len(lemma_links)} edges")


if __name__ == "__main__":
    main()