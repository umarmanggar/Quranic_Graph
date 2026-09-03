"""
Setup pipeline similarity. Seperti src/fatwa/setup.py: :isSimilar cuma tambahan
inkremental di atas islamic_kg yang sudah jadi -- node Ayah/Hadith/Tafsir/Fatwa
(dan semua edge lain) TIDAK disentuh. confirm+delete di sini di-scope cuma ke
edge :isSimilar.

Fail-fast kalau islamic_kg belum punya salah satu dari keempat label sumber
(MATCH di edges.py akan silently no-op kalau target tidak ketemu).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg

from db import graph_connection, run, count, _dsn, DEFAULT_GRAPH
from config import EDGE_LABEL, NODE_SPECS

GRAPH = DEFAULT_GRAPH


def ensure_source_nodes(conn):
    for label, _, _ in NODE_SPECS:
        if count(conn, GRAPH, f"MATCH (n:{label}) RETURN count(*)") == 0:
            raise RuntimeError(
                f"{GRAPH} punya 0 node :{label} -- jalankan src/islamic/main.py "
                f"(dan src/fatwa/main.py) dulu; edge :{EDGE_LABEL} akan gagal MATCH."
            )


def confirm_and_clear(conn):
    n = count(conn, GRAPH, f"MATCH ()-[r:{EDGE_LABEL}]->() RETURN count(r)")
    if n == 0:
        return
    answer = input(
        f"  {n:,} edge :{EDGE_LABEL} sudah ada di {GRAPH}. Hapus semua dan bangun ulang? [y/N]: "
    )
    if answer.strip().lower() not in ("y", "yes"):
        print(f"  Dibatalkan -- edge :{EDGE_LABEL} tidak diubah.")
        sys.exit(0)
    run(conn, f"MATCH ()-[r:{EDGE_LABEL}]->() DELETE r")
    print(f"  {n:,} edge :{EDGE_LABEL} lama dihapus (node tidak disentuh).")


def main():
    # create_elabel butuh autocommit di luar blok cypher() -- pola sama spt islamic/setup.py
    with psycopg.connect(_dsn()) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute('SET search_path = ag_catalog, "$user", public;')
            cur.execute("SELECT to_regclass(%s);", (f'{GRAPH}."{EDGE_LABEL}"',))
            if cur.fetchone()[0] is None:
                cur.execute("SELECT create_elabel(%s, %s);", (GRAPH, EDGE_LABEL))
                print(f"  edge label :{EDGE_LABEL} dibuat.")

    with graph_connection() as conn:
        ensure_source_nodes(conn)
        confirm_and_clear(conn)
    print("similarity setup selesai")


if __name__ == "__main__":
    main()
