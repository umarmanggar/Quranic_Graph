"""
Tambah lemma baru dari TafsirLemma Ibnu Katsir ke Lemma global islamic_kg.
Cuma menambah yang key-nya belum ada. Tidak menyentuh lemma existing.
Dijalankan SEBELUM wordoccurrence_tafsir.py utk Ibnu Katsir.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import graph_connection, run_batch, cypher_rows
from ids import dedup_key

CREATE_LEMMA = """
UNWIND $rows AS row
CREATE (:Lemma {lemma_id: row.lemma_id, text: row.text, pos: row.pos, frequency: row.frequency, source: row.source})
"""


def main():
    with graph_connection() as conn:
        # lemma global yang sudah ada (key + max id)
        existing = cypher_rows(conn, "islamic_kg", "MATCH (l:Lemma) RETURN l.lemma_id, l.text",
                               ["lemma_id", "text"], desc="Lemma global")
        existing_keys = {dedup_key(r["text"]) for r in existing}
        max_id = max((r["lemma_id"] for r in existing), default=-1)

        # lemma Ibnu Katsir dari quran_kg (via TafsirWordOccurrence yg book_id ibnu_katsir)
        ik_lemmas = cypher_rows(conn, "quran_kg",
            "MATCH (w:TafsirWordOccurrence)-[:PART_OF_TAFSIR]->(t:Tafsir {book_id:'tafsir_ibnu_katsir'}) "
            "MATCH (w)-[:HAS_TAFSIR_LEMMA]->(l:TafsirLemma) RETURN DISTINCT l.lemma_id, l.text",
            ["lemma_id", "text"], desc="TafsirLemma Ibnu Katsir")

        new_rows = []
        seen = set()
        counter = max_id + 1
        for r in ik_lemmas:
            key = dedup_key(r["text"])
            if key in existing_keys or key in seen:
                continue
            seen.add(key)
            new_rows.append({"lemma_id": counter, "text": r["text"], "pos": None, "frequency": None, "source": None})
            counter += 1

        print(f"  lemma Ibnu Katsir: {len(ik_lemmas)}, baru (belum ada di global): {len(new_rows)}", flush=True)
        if new_rows:
            run_batch(conn, CREATE_LEMMA, new_rows)
        print(f"Ditambahkan {len(new_rows)} Lemma baru ke global.")


if __name__ == "__main__":
    main()
