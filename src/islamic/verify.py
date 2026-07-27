"""
Verifikasi islamic_kg: hitung node/edge per label/tipe, cek WordOccurrence
total harus PERSIS sama dgn jumlah 3 sumber (tidak ada dedup kata, cuma
Lemma/Root yg di-dedup), cek tidak ada WordOccurrence yatim (tanpa OCCURS_IN),
dan cek tiap HAS_LEMMA/HAS_CANDIDATE selalu punya rank.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import graph_connection, count, DEFAULT_GRAPH

NODES = ["Surah", "Ayah", "Translation", "Koleksi", "Bab", "Hadith",
         "Book", "Tafsir", "WordOccurrence", "Lemma", "Root"]
EDGES = ["PART_OF", "HAS_TRANSLATION", "PART_OF_BOOK", "INTERPRETS",
         "OCCURS_IN", "HAS_LEMMA", "HAS_CANDIDATE", "HAS_ROOT"]

EXPECTED_EXACT = {
    "Surah": 114, "Ayah": 6236, "Translation": 6236,
    "Koleksi": 6, "Bab": 220, "Hadith": 33212,
    "Book": 2, "Tafsir": 7936,
}
EXPECTED_WORDOCCURRENCE = 77432 + 684863 + 1516241  # quran + tafsir + hadith, no cross-domain dedup
NAIVE_LEMMA_SUM = 4817 + 16252 + 14549
NAIVE_ROOT_SUM = 1642 + 3842


def main():
    with graph_connection() as conn:
        print("== node ==")
        counts = {}
        for lb in NODES:
            c = count(conn, DEFAULT_GRAPH, f"MATCH (n:{lb}) RETURN count(n)")
            counts[lb] = c
            flag = ""
            if lb in EXPECTED_EXACT and c != EXPECTED_EXACT[lb]:
                flag = f"  MISMATCH (expected {EXPECTED_EXACT[lb]})"
            print(f"  {lb:16s}: {c:,}{flag}")

        wo_flag = "" if counts["WordOccurrence"] == EXPECTED_WORDOCCURRENCE else \
            f"  MISMATCH (expected exactly {EXPECTED_WORDOCCURRENCE:,})"
        print(f"  -> WordOccurrence exact-sum check: {counts['WordOccurrence']:,} vs {EXPECTED_WORDOCCURRENCE:,}{wo_flag}")
        print(f"  -> Lemma dedup: {counts['Lemma']:,} (naive sum w/o dedup would be {NAIVE_LEMMA_SUM:,})")
        print(f"  -> Root dedup: {counts['Root']:,} (naive sum w/o dedup would be {NAIVE_ROOT_SUM:,})")
        if counts["Lemma"] >= NAIVE_LEMMA_SUM:
            print("  WARNING: Lemma count did not shrink -- dedup may not have run")
        if counts["Root"] >= NAIVE_ROOT_SUM:
            print("  WARNING: Root count did not shrink -- dedup may not have run")

        print("== edge ==")
        for et in EDGES:
            c = count(conn, DEFAULT_GRAPH, f"MATCH ()-[e:{et}]->() RETURN count(e)")
            print(f"  {et:16s}: {c:,}")

        print("== struktur ==")
        orphans = count(conn, DEFAULT_GRAPH,
            "MATCH (w:WordOccurrence) OPTIONAL MATCH (w)-[r:OCCURS_IN]->() "
            "WITH w, r WHERE r IS NULL RETURN count(w)")
        print(f"  WordOccurrence tanpa OCCURS_IN: {orphans:,} (harus 0)")

        no_rank_lemma = count(conn, DEFAULT_GRAPH, "MATCH ()-[e:HAS_LEMMA]->() WHERE e.rank IS NULL RETURN count(e)")
        no_rank_cand = count(conn, DEFAULT_GRAPH, "MATCH ()-[e:HAS_CANDIDATE]->() WHERE e.rank IS NULL RETURN count(e)")
        print(f"  HAS_LEMMA tanpa rank: {no_rank_lemma:,} (harus 0)")
        print(f"  HAS_CANDIDATE tanpa rank: {no_rank_cand:,} (harus 0)")

        print("== per-source WordOccurrence ==")
        for src, expected in [("quran", 77432), ("tafsir", 684863), ("hadith", 1516241)]:
            c = count(conn, DEFAULT_GRAPH, f"MATCH (w:WordOccurrence {{source: '{src}'}}) RETURN count(w)")
            flag = "" if c == expected else f"  MISMATCH (expected {expected:,})"
            print(f"  {src:8s}: {c:,}{flag}")


if __name__ == "__main__":
    main()
