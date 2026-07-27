"""
Migrasi WordOccurrence (hadith) -> islamic_kg. Ini yang paling besar (~1.5jt
node). Arah edge DIBALIK: sumbernya (Hadith)-[:HAS_WORD]->(WordOccurrence),
target (WordOccurrence)-[:OCCURS_IN]->(Hadith) (konvensi terpilih: semua
WordOccurrence nunjuk ke parent-nya). HAS_LEMMA (rank 1) & HAS_CANDIDATE
(rank>=2) dipertahankan apa adanya (rank/frequency asli), lemma_id di-remap
ke Lemma unifikasi.

Koneksi ke DB remote sempat putus di tengah run panjang (>25 menit) -- jadi
tahap tulis (yang berat/lama) pakai resilient_write(): satu koneksi baru per
batch (bukan satu koneksi dipegang selama ~500 batch), dgn retry+reconnect
kalau satu batch gagal. Tiap batch sudah CREATE-only & commit sendiri, jadi
retry cuma re-run batch yang gagal, tidak dobel data.
"""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from tqdm import tqdm

from db import graph_connection, run_chunk, cypher_rows
import remap

BATCH_SIZE = 3000
MAX_RETRIES = 5


def resilient_write(query, rows, size=BATCH_SIZE, max_retries=MAX_RETRIES):
    total = len(rows)
    if total == 0:
        return
    for start in tqdm(range(0, total, size), total=-(-total // size), unit="batch"):
        chunk = rows[start:start + size]
        for attempt in range(1, max_retries + 1):
            try:
                with graph_connection() as conn:
                    run_chunk(conn, query, chunk)
                break
            except Exception as e:
                if attempt == max_retries:
                    raise
                print(f"\n  batch at row {start} failed (attempt {attempt}/{max_retries}): {e!r} -- retrying")
                time.sleep(min(2 ** attempt, 30))


CREATE_WORD = """
UNWIND $rows AS row
MATCH (h:Hadith {hadith_id: row.parent_key})
CREATE (h)<-[:OCCURS_IN]-(:WordOccurrence {
  location: row.location, position: row.position, surface_form: row.surface_form,
  surface_norm: row.surface_norm, n_candidates: row.n_candidates, is_oov: row.is_oov,
  source: row.source
})
"""

LINK_LEMMA = """
UNWIND $rows AS row
MATCH (w:WordOccurrence {location: row.location})
MATCH (l:Lemma {lemma_id: row.lemma_id})
CREATE (w)-[:HAS_LEMMA {rank: row.rank, frequency: row.frequency}]->(l)
"""

LINK_CANDIDATE = """
UNWIND $rows AS row
MATCH (w:WordOccurrence {location: row.location})
MATCH (l:Lemma {lemma_id: row.lemma_id})
CREATE (w)-[:HAS_CANDIDATE {rank: row.rank, frequency: row.frequency}]->(l)
"""


def main():
    with graph_connection() as conn:
        words_raw = cypher_rows(conn, "hadith_kg",
            "MATCH (h:Hadith)-[:HAS_WORD]->(w:WordOccurrence) "
            "RETURN h.hadith_id, w.location, w.position, w.surface_form, w.surface_norm, w.n_candidates, w.is_oov",
            ["hadith_id", "location", "position", "surface_form", "surface_norm", "n_candidates", "is_oov"],
            desc="WordOccurrence (hadith)")

        words = [{
            "location": r["location"], "position": r["position"], "surface_form": r["surface_form"],
            "surface_norm": r["surface_norm"], "n_candidates": r["n_candidates"], "is_oov": r["is_oov"],
            "parent_key": r["hadith_id"], "source": "hadith",
        } for r in words_raw]

        hadith_lemma_id_to_new = remap.old_lemma_id_to_new(
            conn, "hadith_kg", "MATCH (l:Lemma) RETURN l.lemma_id, l.lemma", ["lemma_id", "lemma"],
            "lemma_id", "lemma")

        top_raw = cypher_rows(conn, "hadith_kg",
            "MATCH (w:WordOccurrence)-[e:HAS_LEMMA]->(l:Lemma) RETURN w.location, l.lemma_id, e.rank, e.frequency",
            ["location", "lemma_id", "rank", "frequency"], desc="WordOccurrence-HAS_LEMMA (hadith)")
        top_links = [{
            "location": r["location"], "lemma_id": hadith_lemma_id_to_new[r["lemma_id"]],
            "rank": r["rank"], "frequency": r["frequency"],
        } for r in top_raw]

        cand_raw = cypher_rows(conn, "hadith_kg",
            "MATCH (w:WordOccurrence)-[e:HAS_CANDIDATE]->(l:Lemma) RETURN w.location, l.lemma_id, e.rank, e.frequency",
            ["location", "lemma_id", "rank", "frequency"], desc="WordOccurrence-HAS_CANDIDATE (hadith)")
        cand_links = [{
            "location": r["location"], "lemma_id": hadith_lemma_id_to_new[r["lemma_id"]],
            "rank": r["rank"], "frequency": r["frequency"],
        } for r in cand_raw]

    print("  menulis WordOccurrence (hadith)...", flush=True)
    resilient_write(CREATE_WORD, words)
    print("  menulis HAS_LEMMA (hadith)...", flush=True)
    resilient_write(LINK_LEMMA, top_links)
    print("  menulis HAS_CANDIDATE (hadith)...", flush=True)
    resilient_write(LINK_CANDIDATE, cand_links)

    print(f"WordOccurrence (hadith): {len(words)} nodes + OCCURS_IN")
    print(f"HAS_LEMMA (top-1): {len(top_links)}, HAS_CANDIDATE (alt): {len(cand_links)}")


if __name__ == "__main__":
    main()
