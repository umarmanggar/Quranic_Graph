"""
Edge Fatwa -[:RELATED_QURAN]-> Ayah, Method A saja (regex parse + lookup
nama surah, dgn fallback normalisasi alef/hamza). Port dari
`fatwa_quran_linking_experiment.ipynb` Bagian 3 & 5b.

Target Ayah node di sini adalah salinan Ayah milik islamic_kg (dibuat oleh
src/islamic/surah_ayah.py), BUKAN quran_kg -- islamic_kg satu-satunya graph
yang punya Hadith & Ayah sekaligus, dan Fatwa node cuma ada di islamic_kg.

Sitasi yang gagal di tahap manapun (regex tidak cocok, nama surah tidak
ketemu walau sudah dinormalisasi, atau verse_key hasil parse ternyata tidak
ada di islamic_kg) di-skip -- sesuai instruksi: footnote yang gagal di
Method A dilewat saja, tidak ada Method B/patch manual.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import graph_connection, run_batch, cypher_rows, sqlite_rows
from segmentation import segment_all_books
from classify import split_citations, classify_citation, parse_quran_citation, norm_alef

LINK_RELATED_QURAN = """
UNWIND $rows AS row
MATCH (f:Fatwa {fatwa_id: row.fatwa_id})
MATCH (a:Ayah {verse_key: row.verse_key})
MERGE (f)-[:RELATED_QURAN]->(a)
"""


def load_chapters():
    rows = sqlite_rows("al-quran/quran-metadata-surah-name.sqlite", "SELECT id, name_arabic FROM chapters")
    chapters = {r["name_arabic"]: r["id"] for r in rows}
    chapters_norm = {norm_alef(name): surah_id for name, surah_id in chapters.items()}
    assert len(chapters_norm) == len(chapters), "normalisasi alef bikin nama surah collide -- cek manual"
    return chapters, chapters_norm


def resolve_surah_id(surah_name_raw, chapters, chapters_norm):
    surah_id = chapters.get(surah_name_raw)
    if surah_id is not None:
        return surah_id
    return chapters_norm.get(norm_alef(surah_name_raw))


def collect_citations():
    citations = []
    for fatwa in segment_all_books():
        for entry in fatwa["footnote_entries"]:
            for c in split_citations(entry):
                category, _, _ = classify_citation(c)
                if category != "quran":
                    continue
                citations.append({"fatwa_id": fatwa["fatwa_id"], "text": c})
    return citations


def resolve_rows(citations, chapters, chapters_norm, ayah_verse_keys):
    """Dedup on (fatwa_id, verse_key) -- sama alasannya dgn fatwa_hadith.py:
    satu fatwa sering mengutip ayat yang sama lewat beberapa footnote."""
    seen = set()
    edge_rows, skipped, duplicates = [], 0, 0
    for c in citations:
        surah_name_raw, ayah_num = parse_quran_citation(c["text"])
        if surah_name_raw is None:
            skipped += 1
            continue
        surah_id = resolve_surah_id(surah_name_raw, chapters, chapters_norm)
        if surah_id is None:
            skipped += 1
            continue
        verse_key = f"{surah_id}:{ayah_num}"
        if verse_key not in ayah_verse_keys:
            skipped += 1
            continue
        key = (c["fatwa_id"], verse_key)
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        edge_rows.append({"fatwa_id": key[0], "verse_key": key[1]})
    return edge_rows, skipped, duplicates


def main():
    citations = collect_citations()
    chapters, chapters_norm = load_chapters()
    with graph_connection() as conn:
        ayah_rows = cypher_rows(conn, "islamic_kg", "MATCH (a:Ayah) RETURN a.verse_key", ["verse_key"], desc="Ayah (verse_key)")
        ayah_verse_keys = {r["verse_key"] for r in ayah_rows}
        edge_rows, skipped, duplicates = resolve_rows(citations, chapters, chapters_norm, ayah_verse_keys)
        run_batch(conn, LINK_RELATED_QURAN, edge_rows)

    print(f"RELATED_QURAN: {len(edge_rows)} edge unik dari {len(citations)} sitasi quran "
          f"({skipped} di-skip: regex/surah_resolve/verse_key_not_in_kg, "
          f"{duplicates} duplikat fatwa->ayah yg sama)")


if __name__ == "__main__":
    main()
