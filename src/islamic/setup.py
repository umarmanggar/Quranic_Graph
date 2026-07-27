"""
Setup graph islamic_kg. Beda dari al-quran/setup.py (yang cuma wipe row lewat
`MATCH (n) DETACH DELETE n`): di sini pipeline dirancang untuk full-rebuild
tiap kali dijalankan, jadi lebih bersih & cepat untuk drop_graph() + create_graph()
lagi daripada menghapus baris satu-satu -- DETACH DELETE cuma soft-delete
(MVCC), baris matinya numpuk di tabel fisik tiap kali kita full-rebuild
berulang selama testing, dan CREATE INDEX/VACUUM FULL harus scan semua bloat
itu walau row count logisnya 0. drop_graph()+create_graph() membuang tabel
lama sepenuhnya (metadata-only, cepat) dan membuat tabel baru yang bersih.

(Sempat kelihatan seperti drop_graph/CREATE INDEX "lambat sekali" -- ternyata
itu bukan soal bloat, tapi ada koneksi lama yang masih memegang lock di tabel
WordOccurrence/OCCURS_IN [sisa proses yang belum ditutup]. Begitu lock itu
lepas, drop_graph selesai dalam <1 detik walau tabelnya ratusan MB.)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg

from db import graph_connection, run, _dsn, DEFAULT_GRAPH

GRAPH = DEFAULT_GRAPH
LABELS = [
    "Surah", "Ayah", "Translation",
    "Koleksi", "Bab", "Hadith",
    "Book", "Tafsir",
    "WordOccurrence", "Lemma", "Root",
]


def main():
    with psycopg.connect(_dsn()) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute('SET search_path = ag_catalog, "$user", public;')
            cur.execute("SELECT count(*) FROM ag_graph WHERE name = %s;", (GRAPH,))
            exists = cur.fetchone()[0] > 0
            if exists:
                print(f"  drop_graph({GRAPH})...", flush=True)
                cur.execute("SELECT drop_graph(%s, true);", (GRAPH,))
            print(f"  create_graph({GRAPH})...", flush=True)
            cur.execute("SELECT create_graph(%s);", (GRAPH,))
    print(f"graph {GRAPH} dibuat ulang dari kosong")

    print("  membuat label kosong...", flush=True)
    with graph_connection() as conn:
        for label in LABELS:
            print(f"    {label}", flush=True)
            run(conn, f"CREATE (:{label} {{_dummy: true}})")
        run(conn, "MATCH (n) WHERE n._dummy = true DELETE n")

        print("  membuat GIN index...", flush=True)
        with conn.cursor() as cur:
            for label in LABELS:
                print(f"    {label}", flush=True)
                cur.execute(
                    f'CREATE INDEX IF NOT EXISTS {label.lower()}_props_gin '
                    f'ON {GRAPH}."{label}" USING GIN (properties);'
                )
        conn.commit()
    print(f"label + GIN index siap: {', '.join(LABELS)}")


if __name__ == "__main__":
    main()
