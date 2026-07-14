import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import graph_connection, GRAPH

NODES = ["Book", "Tafsir", "TafsirWordOccurrence", "TafsirLemma"]
EDGES = ["PART_OF_BOOK", "INTERPRETS", "PART_OF_TAFSIR", "HAS_LEMMA"]
EXPECTED = {"Book": 1, "Tafsir": 1738, "PART_OF_BOOK": 1738, "INTERPRETS": 6237}


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
            print(f"  {label:24} {n}{flag}")
        print("edges:")
        for edge in EDGES:
            n = count(conn, f"()-[:{edge}]->()")
            flag = ""
            if edge in EXPECTED:
                flag = " ok" if n == EXPECTED[edge] else f" EXPECTED {EXPECTED[edge]}"
            print(f"  {edge:24} {n}{flag}")


if __name__ == "__main__":
    main()
