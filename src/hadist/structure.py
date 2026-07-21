"""
Tahap 2 - node Koleksi, Bab, Hadith + edge PART_OF (Bab->Koleksi, Hadith->Bab).
Meniru pola surah.py/ayah.py Quran.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import graph_connection, run_batch, analyzed_rows, DEFAULT_GRAPH

ANALYZED = "hadith_analyzed.db"

CREATE_KOLEKSI = """
UNWIND $rows AS row
CREATE (:Koleksi {koleksi_id: row.koleksi_id, name_folder: row.name_folder})
"""

CREATE_BAB = """
UNWIND $rows AS row
CREATE (:Bab {
  bab_id: row.bab_id, bab_number: row.bab_number,
  name_arabic: row.name_arabic, name_latin: row.name_latin
})
"""

LINK_BAB_KOLEKSI = """
UNWIND $rows AS row
MATCH (b:Bab {bab_id: row.bab_id})
MATCH (k:Koleksi {koleksi_id: row.koleksi_id})
CREATE (b)-[:PART_OF]->(k)
"""

CREATE_HADITH = """
UNWIND $rows AS row
CREATE (:Hadith {
  hadith_id: row.hadith_id, nomor: row.nomor,
  arabic_full: row.arabic_full, arabic_matn: row.arabic_matn,
  english_matn: row.english_matn, grade: row.grade
})
"""

LINK_HADITH_BAB = """
UNWIND $rows AS row
MATCH (h:Hadith {hadith_id: row.hadith_id})
MATCH (b:Bab {bab_id: row.bab_id})
CREATE (h)-[:PART_OF]->(b)
"""


def main():
    koleksi = analyzed_rows(ANALYZED, "SELECT koleksi_id, name_folder FROM koleksi")
    bab = analyzed_rows(ANALYZED, "SELECT bab_id, koleksi_id, bab_number, name_arabic, name_latin FROM bab")
    hadith = analyzed_rows(ANALYZED, "SELECT hadith_id, bab_id, nomor, arabic_full, arabic_matn, english_matn, grade FROM hadith")

    with graph_connection(DEFAULT_GRAPH) as conn:
        run_batch(conn, CREATE_KOLEKSI, koleksi)
        run_batch(conn, CREATE_BAB, [{k: r[k] for k in ("bab_id","bab_number","name_arabic","name_latin")} for r in bab])
        run_batch(conn, LINK_BAB_KOLEKSI, [{"bab_id": r["bab_id"], "koleksi_id": r["koleksi_id"]} for r in bab])
        run_batch(conn, CREATE_HADITH, [{k: r[k] for k in ("hadith_id","nomor","arabic_full","arabic_matn","english_matn","grade")} for r in hadith])
        run_batch(conn, LINK_HADITH_BAB, [{"hadith_id": r["hadith_id"], "bab_id": r["bab_id"]} for r in hadith])

    print(f"Koleksi: {len(koleksi)}, Bab: {len(bab)}, Hadith: {len(hadith)} (+ PART_OF edges)")


if __name__ == "__main__":
    main()
