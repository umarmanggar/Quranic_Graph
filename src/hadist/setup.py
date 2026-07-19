"""
Tahap 2 - setup graph hadith_kg.
Beda penting dari setup.py Quran: graph & label BELUM pernah ada, jadi tidak bisa
langsung CREATE INDEX. Di AGE tabel label baru lahir saat node pertama dibuat.
Urutan wajib: buat graph -> buat tiap label kosong -> baru GIN index.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg

from db import graph_connection, run, _dsn, DEFAULT_GRAPH

GRAPH = DEFAULT_GRAPH
LABELS = ["Koleksi", "Bab", "Hadith", "WordOccurrence", "Lemma", "Root"]


def main():
    with psycopg.connect(_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute('SET search_path = ag_catalog, "$user", public;')
            cur.execute("SELECT count(*) FROM ag_graph WHERE name = %s;", (GRAPH,))
            exists = cur.fetchone()[0] > 0
            if not exists:
                cur.execute("SELECT create_graph(%s);", (GRAPH,))
        conn.commit()
    print(f"graph {GRAPH} {'sudah ada' if exists else 'dibuat'}")

    with graph_connection(GRAPH) as conn:
        run(conn, "MATCH (n) DETACH DELETE n")
        # bikin tiap label lahir (tabel eksis) lalu buang node dummy-nya
        for label in LABELS:
            run(conn, f"CREATE (:{label} {{_dummy: true}})")
        run(conn, "MATCH (n) WHERE n._dummy = true DELETE n")

        with conn.cursor() as cur:
            for label in LABELS:
                cur.execute(
                    f'CREATE INDEX IF NOT EXISTS {label.lower()}_props_gin '
                    f'ON {GRAPH}."{label}" USING GIN (properties);'
                )
        conn.commit()
    print(f"label + GIN index siap: {', '.join(LABELS)}")


if __name__ == "__main__":
    main()
