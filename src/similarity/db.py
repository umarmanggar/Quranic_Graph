"""
db helper untuk pipeline similarity (edge :isSimilar). Sama pola dgn
src/fatwa/db.py: BACA node yang sudah ada di islamic_kg (Ayah/Hadith/Tafsir/
Fatwa) dan TULIS edge :isSimilar ke graph yang sama -- run()/run_batch()
menolak graph selain islamic_kg supaya tidak mungkin ke-tulis tidak sengaja ke
graph lain. Tidak ada node baru yang dibuat modul ini.
"""
import os
import json
from contextlib import contextmanager

import psycopg
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

DEFAULT_GRAPH = "islamic_kg"


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
            cur.execute("SET max_parallel_workers_per_gather = 0;")
        conn.commit()
        yield conn
    finally:
        conn.close()


def run(conn, query, graph=DEFAULT_GRAPH):
    if graph != DEFAULT_GRAPH:
        raise ValueError(f"run() only writes to {DEFAULT_GRAPH!r}, got graph={graph!r}")
    with conn.cursor() as cur:
        cur.execute(f"SELECT * FROM cypher('{graph}', $$ {query} $$) AS (v agtype);")
    conn.commit()


def run_batch(conn, query, rows, graph=DEFAULT_GRAPH, size=500):
    if graph != DEFAULT_GRAPH:
        raise ValueError(f"run_batch() only writes to {DEFAULT_GRAPH!r}, got graph={graph!r}")
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


def _decode(value):
    if value is None:
        return None
    s = str(value)
    if s == "":
        return None
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return s


def cypher_rows(conn, graph, query, columns, desc=None):
    """Read-only: jalankan MATCH...RETURN terhadap `graph` dan decode kolom
    agtype sesuai urutan `columns`. Returns list[dict]."""
    if desc:
        print(f"  membaca {desc} dari {graph}...", flush=True)
    col_sql = ", ".join(f"{c} agtype" for c in columns)
    with conn.cursor() as cur:
        cur.execute(f"SELECT * FROM cypher('{graph}', $$ {query} $$) AS ({col_sql});")
        rows = cur.fetchall()
    if desc:
        print(f"    -> {len(rows):,} baris, decoding...", flush=True)
    return [
        {col: _decode(val) for col, val in zip(columns, row)}
        for row in tqdm(rows, unit="row", desc=f"  decode {desc}" if desc else "decode", leave=False)
    ]


def count(conn, graph, query):
    with conn.cursor() as cur:
        cur.execute(f"SELECT * FROM cypher('{graph}', $$ {query} $$) AS (v agtype);")
        return int(str(cur.fetchone()[0]))
