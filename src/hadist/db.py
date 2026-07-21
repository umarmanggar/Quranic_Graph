"""
db helper untuk loader hadith. Meniru src/db.py milik repo (psycopg v3, batching
UNWIND + parameter agtype supaya teks arab aman dari escaping). Beda: GRAPH bisa
di-pass per-call, karena hadith pakai graph 'hadith_kg' bukan 'quran_kg'.
Koneksi & .env sama persis dgn punya Quran.
"""
import os
import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager

import psycopg
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

DEFAULT_GRAPH = "hadith_kg"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _dsn():
    return (
        f"host={os.environ['DB_HOST']} "
        f"port={os.environ.get('DB_PORT', '5432')} "
        f"dbname={os.environ['DB_NAME']} "
        f"user={os.environ['DB_USER']} "
        f"password={os.environ['DB_PASSWORD']}"
    )


@contextmanager
def graph_connection(graph=DEFAULT_GRAPH):
    conn = psycopg.connect(_dsn())
    try:
        with conn.cursor() as cur:
            cur.execute('SET search_path = ag_catalog, "$user", public;')
        conn.commit()
        conn._graph = graph  # simpan supaya run/run_batch tahu graph mana
        yield conn
    finally:
        conn.close()


def run(conn, query):
    graph = getattr(conn, "_graph", DEFAULT_GRAPH)
    with conn.cursor() as cur:
        cur.execute(f"SELECT * FROM cypher('{graph}', $$ {query} $$) AS (v agtype);")
    conn.commit()


def run_batch(conn, query, rows, size=500):
    graph = getattr(conn, "_graph", DEFAULT_GRAPH)
    total = len(rows)
    if total == 0:
        return
    with conn.cursor() as cur:
        for start in tqdm(range(0, total, size), total=-(-total // size), unit="batch", leave=False):
            chunk = rows[start:start + size]
            cur.execute(
                f"SELECT * FROM cypher('{graph}', $$ {query} $$, %s::agtype) AS (v agtype);",
                (json.dumps({"rows": chunk}),),
            )
            conn.commit()


def analyzed_rows(db_path, query):
    """baca dari hadith_analyzed.db (output tahap 1)."""
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(query)]
    finally:
        con.close()
