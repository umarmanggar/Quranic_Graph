import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import graph_connection, GRAPH

NODES = ["Surah", "Ayah", "WordOccurrence", "Root", "Lemma", "Translation"]
EDGES = ["PART_OF", "OCCURS_IN", "HAS_ROOT", "HAS_LEMMA", "HAS_TRANSLATION"]
EXPECTED = {"Surah": 114, "Ayah": 6236, "Translation": 6236}


def count(conn, pattern):
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT * FROM cypher('{GRAPH}', $$ MATCH {pattern} RETURN count(*) $$) AS (n agtype);"
        )
        return int(cur.fetchone()[0])


def main():
    with graph_connection() as conn:
        print("nodes:")
        for label in NODES:
            n = count(conn, f"(:{label})")
            flag = ""
            if label in EXPECTED:
                flag = " ok" if n == EXPECTED[label] else f" EXPECTED {EXPECTED[label]}"
            print(f"  {label:16} {n}{flag}")
        print("edges:")
        for edge in EDGES:
            print(f"  {edge:16} {count(conn, f'()-[:{edge}]->()')}")


if __name__ == "__main__":
    main()