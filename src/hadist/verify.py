"""
Tahap 2 - verifikasi. Hitung node/edge per label, bandingkan dgn ekspektasi gate.
OOV harus ~5.6%, ambigu ~32.6% (dari gate2). Kalau meleset jauh -> ada yg salah.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import graph_connection, DEFAULT_GRAPH


def count(conn, cypher):
    with conn.cursor() as cur:
        cur.execute(f"SELECT * FROM cypher('{DEFAULT_GRAPH}', $$ {cypher} $$) AS (v agtype);")
        return int(str(cur.fetchone()[0]))


def main():
    with graph_connection(DEFAULT_GRAPH) as conn:
        labels = ["Koleksi", "Bab", "Hadith", "WordOccurrence", "Lemma", "Root"]
        print("== node ==")
        for lb in labels:
            print(f"  {lb:16s}: {count(conn, f'MATCH (n:{lb}) RETURN count(n)'):,}")

        print("== edge ==")
        for et in ["PART_OF", "HAS_WORD", "HAS_LEMMA", "HAS_CANDIDATE", "HAS_ROOT"]:
            print(f"  {et:16s}: {count(conn, f'MATCH ()-[e:{et}]->() RETURN count(e)'):,}")

        total = count(conn, "MATCH (w:WordOccurrence) RETURN count(w)")
        oov = count(conn, "MATCH (w:WordOccurrence) WHERE w.is_oov = true RETURN count(w)")
        amb = count(conn, "MATCH (w:WordOccurrence) WHERE w.n_candidates > 1 RETURN count(w)")
        print("== sanity (bandingkan gate2) ==")
        print(f"  OOV   : {oov/total:.1%} (harusnya ~5.6%)")
        print(f"  ambigu: {amb/total:.1%} (harusnya ~32.6%)")


if __name__ == "__main__":
    main()
