"""
Edge Fatwa -[:RELATED_HADITH]-> Hadith, Method A saja (exact match by
number). Port dari `fatwa_hadith_linking_experiment.ipynb` Bagian 2-3.

Nama edge sengaja RELATED_HADITH (bukan CITES), konsisten dgn
src/islamic/hadith_tafsir.py -- walau di sini Method A itu exact match
deterministik (bukan fuzzy), tetap dipertahankan sesuai penamaan yang sudah
ada di islamic_kg.

Join langsung ke Hadith node islamic_kg lewat (Koleksi.name_folder, nomor
ternormalisasi) -- TIDAK lewat LK-Hadith-Corpus/text-matching seperti
hadith_tafsir.py, karena node Hadith di islamic_kg terbukti berasal dari
sumber yang sama persis dgn yang dipakai notebook eksperimen (lihat
note_hadith_islamic_kg.md di root project). Sitasi yang gagal (0 atau >1
match) di-skip, bukan fail-fast -- sesuai instruksi: footnote yang gagal di
Method A dilewat saja.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import graph_connection, run_batch, cypher_rows
from segmentation import segment_all_books
from classify import split_citations, classify_citation, normalize_nomor

LINK_RELATED_HADITH = """
UNWIND $rows AS row
MATCH (f:Fatwa {fatwa_id: row.fatwa_id})
MATCH (h:Hadith {hadith_id: row.hadith_id})
MERGE (f)-[:RELATED_HADITH]->(h)
"""


def build_hadith_index(conn):
    rows = cypher_rows(
        conn, "islamic_kg",
        "MATCH (h:Hadith)-[:PART_OF]->(:Bab)-[:PART_OF]->(k:Koleksi) "
        "RETURN k.name_folder, h.nomor, h.hadith_id",
        ["name_folder", "nomor", "hadith_id"],
        desc="Hadith (utk index nomor)",
    )
    index = {}
    for r in rows:
        key = (r["name_folder"], normalize_nomor(r["nomor"]))
        index.setdefault(key, []).append(r["hadith_id"])
    return index


def collect_citations():
    citations = []
    for fatwa in segment_all_books():
        for entry in fatwa["footnote_entries"]:
            for c in split_citations(entry):
                category, collection, hadith_num = classify_citation(c)
                if category != "hadith_with_number":
                    continue
                citations.append({
                    "fatwa_id": fatwa["fatwa_id"], "collection": collection, "hadith_num": hadith_num,
                })
    return citations


def resolve_rows(citations, hadith_index):
    """Dedup on (fatwa_id, hadith_id): satu fatwa sering mengutip hadits yang
    sama lewat beberapa footnote berbeda -- MERGE di Cypher sudah bikin ini
    jadi satu edge juga, tapi dedup di sini supaya angka "edge dibuat" yang
    di-print cocok dgn jumlah edge sungguhan di graph (bukan jumlah sitasi
    yg diproses)."""
    seen = set()
    edge_rows, skipped, duplicates = [], 0, 0
    for c in citations:
        hits = hadith_index.get((c["collection"], normalize_nomor(c["hadith_num"])), [])
        if len(hits) != 1:
            skipped += 1
            continue
        key = (c["fatwa_id"], hits[0])
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        edge_rows.append({"fatwa_id": key[0], "hadith_id": key[1]})
    return edge_rows, skipped, duplicates


def main():
    citations = collect_citations()
    with graph_connection() as conn:
        hadith_index = build_hadith_index(conn)
        edge_rows, skipped, duplicates = resolve_rows(citations, hadith_index)
        run_batch(conn, LINK_RELATED_HADITH, edge_rows)

    print(f"RELATED_HADITH: {len(edge_rows)} edge unik dari {len(citations)} sitasi hadith_with_number "
          f"({skipped} di-skip: no_match/ambiguous, {duplicates} duplikat fatwa->hadith yg sama)")


if __name__ == "__main__":
    main()
