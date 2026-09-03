"""
Verifikasi subgraph :isSimilar di islamic_kg. Pola sama spt src/*/verify.py:
hitung edge, breakdown per kombinasi label, histogram skor, cek invariant
(no self-loop, arah selalu sesuai prioritas label), contoh edge skor teratas.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import graph_connection, count, cypher_rows, DEFAULT_GRAPH
from config import EDGE_LABEL, LABEL_PRIORITY, THRESHOLD

GRAPH = DEFAULT_GRAPH
COMBOS = [(a, b) for i, a in enumerate(LABEL_PRIORITY) for b in LABEL_PRIORITY[i:]]


def main():
    with graph_connection() as conn:
        total = count(conn, GRAPH, f"MATCH ()-[r:{EDGE_LABEL}]->() RETURN count(r)")
        print(f":{EDGE_LABEL} total: {total:,}")
        if total == 0:
            return

        print("== per kombinasi label ==")
        seen = 0
        for a, b in COMBOS:
            c = count(conn, GRAPH,
                      f"MATCH (:{a})-[r:{EDGE_LABEL}]->(:{b}) RETURN count(r)")
            seen += c
            print(f"  {a}-{b:8s}: {c:,}")
        print(f"  (jumlah kombinasi = {seen:,}; harus == total {total:,})")

        print("== histogram skor ==")
        for lo in [0.70, 0.75, 0.80, 0.85, 0.90, 0.95]:
            c = count(conn, GRAPH,
                      f"MATCH ()-[r:{EDGE_LABEL}]->() WHERE r.score >= {lo} AND r.score < {lo + 0.05} "
                      f"RETURN count(r)")
            print(f"  [{lo:.2f}, {lo + 0.05:.2f}): {c:,}")

        print("== invariant ==")
        loops = count(conn, GRAPH,
                      f"MATCH (n)-[r:{EDGE_LABEL}]->(n) RETURN count(r)")
        print(f"  self-loop: {loops:,} (harus 0)")
        below = count(conn, GRAPH,
                      f"MATCH ()-[r:{EDGE_LABEL}]->() WHERE r.score < {THRESHOLD} RETURN count(r)")
        print(f"  edge di bawah THRESHOLD {THRESHOLD}: {below:,} (harus 0)")

        # arah: tidak boleh ada edge dgn src prioritas label > tgt
        bad_dir = 0
        for i, a in enumerate(LABEL_PRIORITY):
            for b in LABEL_PRIORITY[:i]:
                bad_dir += count(conn, GRAPH,
                                 f"MATCH (:{a})-[r:{EDGE_LABEL}]->(:{b}) RETURN count(r)")
        print(f"  edge arah salah (prioritas label terbalik): {bad_dir:,} (harus 0)")

        print("== 5 edge skor tertinggi ==")
        top = cypher_rows(
            conn, GRAPH,
            f"MATCH (a)-[r:{EDGE_LABEL}]->(b) RETURN labels(a)[0], a, labels(b)[0], b, r.score "
            f"ORDER BY r.score DESC LIMIT 5",
            ["la", "a", "lb", "b", "score"],
        )
        for t in top:
            print(f"  {t['score']:.4f}  {t['la']} <-> {t['lb']}")


if __name__ == "__main__":
    main()
