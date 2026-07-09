import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import graph_connection, run, GRAPH

LABELS = ["Surah", "Ayah", "WordOccurrence", "Root", "Lemma", "Translation"]


def main():
    with graph_connection() as conn:
        run(conn, "MATCH (n) DETACH DELETE n")
        with conn.cursor() as cur:
            for label in LABELS:
                cur.execute(
                    f'CREATE INDEX IF NOT EXISTS {label.lower()}_props_gin '
                    f'ON {GRAPH}."{label}" USING GIN (properties);'
                )
        conn.commit()
    print("graph cleared, GIN indexes ready")


if __name__ == "__main__":
    main()