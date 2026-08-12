"""
Load RELATED_HADITH edge dari CSV kandidat Ibnu Katsir ke islamic_kg.
Baca CSV -> MATCH Tafsir + Hadith -> MERGE edge (idempoten, aman diulang).

Edge: (Tafsir)-[:RELATED_HADITH {score, fragment, trigger_label, rank, source}]->(Hadith)

Jalankan dari folder yang punya db.py (src/islamic).
    python load_related_hadith_ibnu_katsir.py
"""
import sys
import csv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import graph_connection, run_batch

CSV_PATH = "/home/umarmanggar/Projects/Quranic_Graph/data/tafsir/ibnu_katsir_hadith_candidates.csv"

MERGE_EDGE = """
UNWIND $rows AS row
MATCH (t:Tafsir {tafsir_id: row.tafsir_id})
MATCH (h:Hadith {hadith_id: row.hadith_id})
MERGE (t)-[r:RELATED_HADITH]->(h)
SET r.score = row.score, r.fragment = row.fragment,
    r.trigger_label = row.trigger_label, r.rank = row.rank,
    r.source = 'ibnu_katsir_arabic'
"""


def main():
    rows = []
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append({
                "tafsir_id": r["tafsir_id"],
                "hadith_id": int(r["hadith_id"]),
                "score": float(r["score"]),
                "fragment": r["fragment"],
                "trigger_label": r["trigger_label"],
                "rank": int(r["rank"]),
            })

    print(f"  baris CSV: {len(rows)}", flush=True)
    with graph_connection() as conn:
        run_batch(conn, MERGE_EDGE, rows)
    print(f"RELATED_HADITH (Ibnu Katsir): {len(rows)} edge di-MERGE.")


if __name__ == "__main__":
    main()
