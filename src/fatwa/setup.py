"""
Setup pipeline fatwa. Beda dari islamic/setup.py (yang confirm+drop_graph
SELURUH islamic_kg): di sini Fatwa cuma tambahan inkremental di atas
islamic_kg yang sudah dibangun (Hadith/Ayah/Tafsir/dst harus tetap utuh),
jadi confirm+delete di sini di-scope cuma ke label :Fatwa (dan lewat
DETACH DELETE, edge RELATED_HADITH/RELATED_QURAN yang menempel padanya) --
node lain sama sekali tidak disentuh.

Fail-fast kalau islamic_kg belum punya Hadith/Ayah node (RELATED_HADITH/
RELATED_QURAN akan silently no-op kalau MATCH-nya tidak ketemu apa-apa),
mirip pola guard `Ayah` di src/tafsir/setup.py.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import graph_connection, run, count, DEFAULT_GRAPH

GRAPH = DEFAULT_GRAPH
LABELS = ["Fatwa"]


def ensure_source_nodes(conn):
    if count(conn, GRAPH, "MATCH (n:Hadith) RETURN count(*)") == 0:
        raise RuntimeError(
            f"{GRAPH} has 0 Hadith nodes - run src/islamic/main.py first; "
            "RELATED_HADITH edges would silently fail to match."
        )
    if count(conn, GRAPH, "MATCH (n:Ayah) RETURN count(*)") == 0:
        raise RuntimeError(
            f"{GRAPH} has 0 Ayah nodes - run src/islamic/main.py first; "
            "RELATED_QURAN edges would silently fail to match."
        )


def ensure_labels(conn):
    with conn.cursor() as cur:
        for label in LABELS:
            cur.execute("SELECT to_regclass(%s);", (f'{GRAPH}."{label}"',))
            if cur.fetchone()[0] is None:
                cur.execute("SELECT create_vlabel(%s, %s);", (GRAPH, label))
            cur.execute(
                f'CREATE INDEX IF NOT EXISTS {label.lower()}_props_gin '
                f'ON {GRAPH}."{label}" USING GIN (properties);'
            )
    conn.commit()


def confirm_clear(answer):
    return answer.strip().lower() in ("y", "yes")


def confirm_and_clear(conn):
    n = count(conn, GRAPH, "MATCH (f:Fatwa) RETURN count(*)")
    if n == 0:
        return
    answer = input(
        f"  {n:,} Fatwa node sudah ada di {GRAPH}. "
        f"Hapus semua dan bangun ulang? [y/N]: "
    )
    if not confirm_clear(answer):
        print("  Dibatalkan -- subgraph Fatwa tidak diubah.")
        sys.exit(0)
    run(conn, "MATCH (f:Fatwa) DETACH DELETE f")
    print(f"  {n:,} Fatwa node lama (+ edge RELATED_HADITH/RELATED_QURAN terkait) dihapus.")


def main():
    with graph_connection() as conn:
        ensure_source_nodes(conn)
        ensure_labels(conn)
        confirm_and_clear(conn)
    print("fatwa setup selesai")


if __name__ == "__main__":
    main()
