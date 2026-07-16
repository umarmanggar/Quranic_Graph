import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import graph_connection, run_batch, GRAPH

LABELS = ["TafsirLemma", "TafsirWordOccurrence", "Tafsir", "Book"]

DELETE_WORDS = """
UNWIND $rows AS row
MATCH (b:Book {book_id: row.book_id})<-[:PART_OF_BOOK]-(:Tafsir)<-[:PART_OF_TAFSIR]-(w:TafsirWordOccurrence)
DETACH DELETE w
"""

DELETE_TAFSIR = """
UNWIND $rows AS row
MATCH (b:Book {book_id: row.book_id})<-[:PART_OF_BOOK]-(t:Tafsir)
DETACH DELETE t
"""

DELETE_BOOK = """
UNWIND $rows AS row
MATCH (b:Book {book_id: row.book_id})
DETACH DELETE b
"""

DROP_ORPHAN_LEMMA = """
DELETE FROM {g}."TafsirLemma" tl
WHERE NOT EXISTS (
  SELECT 1 FROM {g}."HAS_TAFSIR_LEMMA" e WHERE e.end_id = tl.id
)
"""


def ensure_labels(conn):
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT * FROM cypher('{GRAPH}', $$ MATCH (n:Ayah) RETURN count(*) $$) AS (n agtype);"
        )
        if int(cur.fetchone()[0]) == 0:
            raise RuntimeError(
                "quran_kg has 0 Ayah nodes - run al-quran loader first; "
                "INTERPRETS edges would silently fail to match."
            )
        for label in LABELS:
            cur.execute("SELECT to_regclass(%s);", (f'{GRAPH}."{label}"',))
            if cur.fetchone()[0] is None:
                cur.execute("SELECT create_vlabel(%s, %s);", (GRAPH, label))
            cur.execute(
                f'CREATE INDEX IF NOT EXISTS {label.lower()}_props_gin '
                f'ON {GRAPH}."{label}" USING GIN (properties);'
            )
    conn.commit()


def drop_orphan_lemmas(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s);", (f'{GRAPH}."HAS_TAFSIR_LEMMA"',))
        if cur.fetchone()[0] is None:
            return 0
        cur.execute(DROP_ORPHAN_LEMMA.format(g=GRAPH))
        n = cur.rowcount
    conn.commit()
    return n


def main(book_id):
    rows = [{"book_id": book_id}]
    with graph_connection() as conn:
        ensure_labels(conn)
        run_batch(conn, DELETE_WORDS, rows)
        run_batch(conn, DELETE_TAFSIR, rows)
        run_batch(conn, DELETE_BOOK, rows)
        orphans = drop_orphan_lemmas(conn)
    print(f"cleared subgraph for {book_id}, orphan lemmas removed: {orphans}")