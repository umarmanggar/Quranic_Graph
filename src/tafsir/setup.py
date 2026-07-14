import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import graph_connection, run, GRAPH

LABELS = ["TafsirLemma", "TafsirWordOccurrence", "Tafsir", "Book"]


def main():
    with graph_connection() as conn:
        for label in LABELS:
            run(conn, f"MATCH (n:{label}) DETACH DELETE n")
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM cypher('{GRAPH}', $$ MATCH (n:Ayah) RETURN count(*) $$) AS (n agtype);"
            )
            ayah_count = int(cur.fetchone()[0])
            if ayah_count == 0:
                raise RuntimeError(
                    "quran_kg has 0 Ayah nodes - run Quranic_Graph/src/al-quran/main.py first; "
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
    print("tafsir labels cleared, GIN indexes ready")


if __name__ == "__main__":
    main()
