import os
import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager

import psycopg
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

GRAPH = "quran_kg"
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
def graph_connection():
    conn = psycopg.connect(_dsn())
    try:
        with conn.cursor() as cur:
            cur.execute('SET search_path = ag_catalog, "$user", public;')
        conn.commit()
        yield conn
    finally:
        conn.close()


def run(conn, query):
    with conn.cursor() as cur:
        cur.execute(f"SELECT * FROM cypher('{GRAPH}', $$ {query} $$) AS (v agtype);")
    conn.commit()


def run_batch(conn, query, rows, size=500):
    total = len(rows)
    with conn.cursor() as cur:
        for start in tqdm(range(0, total, size), total=-(-total // size), unit="batch", leave=False):
            chunk = rows[start:start + size]
            cur.execute(
                f"SELECT * FROM cypher('{GRAPH}', $$ {query} $$, %s::agtype) AS (v agtype);",
                (json.dumps({"rows": chunk}),),
            )
            conn.commit()


def sqlite_rows(filename, query):
    con = sqlite3.connect(DATA_DIR / filename)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(query)]
    finally:
        con.close()
