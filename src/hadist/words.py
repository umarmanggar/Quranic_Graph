"""
Tahap 2 - node WordOccurrence + edge HAS_WORD, HAS_LEMMA (top-1), HAS_CANDIDATE (alt).
Bagian terberat: ~1.47jt node. Edge HAS_LEMMA & HAS_CANDIDATE bawa properti rank+frequency
(opsi B: kandidat sbg edge, bukan node). OOV -> node dibuat tanpa edge lema.

location = 'hadith_id:position', jadi key MATCH edge (meniru 'location' Quran).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import graph_connection, run_batch, analyzed_rows, DEFAULT_GRAPH

ANALYZED = "hadith_analyzed.db"

CREATE_WORD = """
UNWIND $rows AS row
MATCH (h:Hadith {hadith_id: row.hadith_id})
CREATE (h)-[:HAS_WORD]->(:WordOccurrence {
  location: row.location,
  position: row.position,
  surface_form: row.surface_form,
  surface_norm: row.surface_norm,
  n_candidates: row.n_candidates,
  is_oov: row.is_oov
})
"""

# top-1: HAS_LEMMA dgn rank 1
LINK_TOP = """
UNWIND $rows AS row
MATCH (w:WordOccurrence {location: row.location})
MATCH (l:Lemma {lemma_id: row.lemma_id})
CREATE (w)-[:HAS_LEMMA {rank: 1, frequency: row.frequency}]->(l)
"""

# alternatif: HAS_CANDIDATE dgn rank>=2
LINK_CAND = """
UNWIND $rows AS row
MATCH (w:WordOccurrence {location: row.location})
MATCH (l:Lemma {lemma_id: row.lemma_id})
CREATE (w)-[:HAS_CANDIDATE {rank: row.rank, frequency: row.frequency}]->(l)
"""


def main():
    occ = analyzed_rows(ANALYZED,
        "SELECT location, hadith_id, position, surface_form, surface_norm, "
        "n_candidates, is_oov, top_lemma_id, top_frequency FROM word_occurrence")

    words = [{
        "location": r["location"], "hadith_id": r["hadith_id"],
        "position": r["position"], "surface_form": r["surface_form"],
        "surface_norm": r["surface_norm"], "n_candidates": r["n_candidates"],
        "is_oov": bool(r["is_oov"]),
    } for r in occ]

    top_links = [{
        "location": r["location"], "lemma_id": r["top_lemma_id"],
        "frequency": r["top_frequency"],
    } for r in occ if r["top_lemma_id"] is not None]

    cand = analyzed_rows(ANALYZED,
        "SELECT location, rank, lemma_id, frequency FROM word_candidate")
    cand_links = [{
        "location": r["location"], "rank": r["rank"],
        "lemma_id": r["lemma_id"], "frequency": r["frequency"],
    } for r in cand]

    with graph_connection(DEFAULT_GRAPH) as conn:
        run_batch(conn, CREATE_WORD, words)
        run_batch(conn, LINK_TOP, top_links)
        run_batch(conn, LINK_CAND, cand_links)

    print(f"WordOccurrence: {len(words)} nodes (+HAS_WORD)")
    print(f"HAS_LEMMA (top-1): {len(top_links)}, HAS_CANDIDATE (alt): {len(cand_links)}")


if __name__ == "__main__":
    main()
