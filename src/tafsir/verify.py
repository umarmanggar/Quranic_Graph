import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import graph_connection, GRAPH
from books import BOOKS

LAYER1_HAS_LEMMA = 72507


def scalar(conn, query):
    with conn.cursor() as cur:
        cur.execute(f"SELECT * FROM cypher('{GRAPH}', $$ {query} $$) AS (n agtype);")
        return int(cur.fetchone()[0])


def main(book_id=None):
    with graph_connection() as conn:
        print("per book:")
        for bid in BOOKS:
            tafsir = scalar(conn, f"MATCH (:Tafsir {{book_id: '{bid}'}}) RETURN count(*)")
            if tafsir == 0:
                print(f"  {bid:20} not loaded")
                continue
            interprets = scalar(
                conn,
                f"MATCH (:Tafsir {{book_id: '{bid}'}})-[r:INTERPRETS]->(:Ayah) RETURN count(r)",
            )
            ayah = scalar(
                conn,
                f"MATCH (:Tafsir {{book_id: '{bid}'}})-[:INTERPRETS]->(a:Ayah) "
                f"RETURN count(DISTINCT a)",
            )
            words = scalar(
                conn,
                f"MATCH (:Tafsir {{book_id: '{bid}'}})<-[:PART_OF_TAFSIR]-(w) RETURN count(w)",
            )
            flag = "" if ayah == 6236 else f"  AYAH COVERAGE {ayah}/6236"
            print(f"  {bid:20} tafsir={tafsir:5} interprets={interprets:5} "
                  f"words={words:7}{flag}")

        print("global:")
        print(f"  Book                 {scalar(conn, 'MATCH (:Book) RETURN count(*)')}")
        print(f"  TafsirLemma          {scalar(conn, 'MATCH (:TafsirLemma) RETURN count(*)')}")

        l1 = scalar(conn, "MATCH ()-[r:HAS_LEMMA]->() RETURN count(r)")
        ok = " ok" if l1 == LAYER1_HAS_LEMMA else f" EXPECTED {LAYER1_HAS_LEMMA} - LAYER 1 CONTAMINATED"
        print(f"  HAS_LEMMA (layer 1)  {l1}{ok}")