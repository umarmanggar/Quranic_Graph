"""
Edge Tafsir -[:RELATED_HADITH]-> Hadith, dari kandidat hasil fuzzy-matching +
manual review (lihat Tafsir/hadith_tafsir_linking.ipynb di luar repo ini).
Tidak ada node baru di sini -- Hadith & Tafsir sudah ada di islamic_kg
(masing-masing dari koleksi_bab_hadith.py & book_tafsir.py), modul ini cuma
MATCH keduanya dan MERGE edge baru.

Nama edge sengaja RELATED_HADITH, bukan CITES: hadith_id hasil fuzzy-match
dari LK-Hadith-Corpus belum tentu persis hadits yang benar-benar dirujuk di
teks tafsir.

Kandidat CSV pakai hadith_id gaya LK-Hadith-Corpus ("Bukhari:2:33" dari
Chapter_Number:Hadith_number), tapi skema penomoran itu TIDAK cocok dengan
kolom nomor/bab_number pada Hadith node islamic_kg (cuma ~50% baris ketemu
kalau di-join lewat angka). Sudah diverifikasi manual: join yang andal adalah
lewat (koleksi.name_folder, arabic_matn ternormalisasi) -- exact match 125/127
baris, 0 ambigu. 2 baris sisanya isinya cuma potongan rujukan silang
"بِهَذَا‏.‏" di korpus asli (bukan matn sungguhan), jadi memang tidak match ke
node manapun -- di-skip + di-log, bukan fail-fast, karena itu memang bukan
data yang valid untuk dihubungkan.
"""
import sys
import csv
import re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import graph_connection, run_batch, cypher_rows

# db.py's DATA_DIR resolves one level too shallow for this subpackage (src/data
# instead of Quranic_Graph/data), so path is computed directly here instead.
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
CSV_PATH = DATA_DIR / "tafsir" / "hadith_tafsir_edge_candidates_selected.csv"
TAFSIR_PREFIX = "as_saadi"  # kandidat cuma digenerate dari id-tafsir-as-saadi.db

DIACRITICS = re.compile(r"[ً-ٰٟۖ-ۭ]")
WS = re.compile(r"\s+")

LINK_RELATED_HADITH = """
UNWIND $rows AS row
MATCH (t:Tafsir {tafsir_id: row.tafsir_id})
MATCH (h:Hadith {hadith_id: row.hadith_id})
MERGE (t)-[r:RELATED_HADITH {trigger_label: row.trigger_label, fragment: row.fragment}]->(h)
SET r.rank = row.rank, r.score = row.score
"""


def normalize_matn(text):
    if not text:
        return ""
    t = DIACRITICS.sub("", text)
    return WS.sub(" ", t).strip()


def load_candidates():
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def build_hadith_index(conn):
    rows = cypher_rows(
        conn, "islamic_kg",
        "MATCH (h:Hadith)-[:PART_OF]->(:Bab)-[:PART_OF]->(k:Koleksi) "
        "RETURN h.hadith_id, k.name_folder, h.arabic_matn",
        ["hadith_id", "name_folder", "arabic_matn"],
        desc="Hadith (utk index matn)",
    )
    index = {}
    for r in rows:
        key = (r["name_folder"], normalize_matn(r["arabic_matn"]))
        index.setdefault(key, []).append(r["hadith_id"])
    return index


def resolve_rows(candidates, hadith_index):
    edge_rows, skipped = [], []
    for c in candidates:
        key = (c["collection"], normalize_matn(c["arabic_matn"]))
        hits = hadith_index.get(key)
        if not hits or len(hits) != 1:
            skipped.append(c["hadith_id"])
            continue
        edge_rows.append({
            "tafsir_id": f"{TAFSIR_PREFIX}:{c['tafsir_group_ayah_key']}",
            "hadith_id": hits[0],
            "rank": int(c["rank"]),
            "score": float(c["score"]),
            "trigger_label": c["trigger_label"],
            "fragment": c["fragment"],
        })
    return edge_rows, skipped


def main():
    candidates = load_candidates()
    with graph_connection() as conn:
        hadith_index = build_hadith_index(conn)
        edge_rows, skipped = resolve_rows(candidates, hadith_index)
        run_batch(conn, LINK_RELATED_HADITH, edge_rows)

    print(f"RELATED_HADITH: {len(edge_rows)} edge dari {len(candidates)} baris kandidat")
    if skipped:
        print(f"  di-skip ({len(skipped)}): {', '.join(skipped)}")


if __name__ == "__main__":
    main()
