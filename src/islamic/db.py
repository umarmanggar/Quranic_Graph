"""
db helper untuk pipeline islamic_kg. Beda dari src/db.py dan src/hadist/db.py:
pipeline ini BACA dari dua graph yang sudah ada (quran_kg, hadith_kg) dan TULIS
ke graph ketiga yang baru (islamic_kg) -- jadi nama graph selalu eksplisit per
panggilan, bukan konstanta modul.

run()/run_batch() sengaja menolak graph selain islamic_kg supaya sumber data
(quran_kg/hadith_kg) tidak mungkin ke-tulis tidak sengaja -- baca lewat
cypher_rows() (read-only, MATCH...RETURN) untuk graph manapun.
"""
import os
import json
from pathlib import Path
from contextlib import contextmanager

import psycopg
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

DEFAULT_GRAPH = "islamic_kg"
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
            # Server punya /dev/shm kecil (khas kontainer Docker default) -- query
            # besar yang memicu parallel worker gagal alokasi dynamic shared
            # memory ("No space left on device" walau database size cuma ~2GB).
            # Matikan parallel query per sesi supaya semua query jalan serial.
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


def run_chunk(conn, query, rows, graph=DEFAULT_GRAPH):
    """Single-chunk write, no internal batching/looping (caller controls chunking
    and connection lifetime -- used by callers that need to reconnect per chunk,
    e.g. wordoccurrence_hadith.py's resilient_write, since the remote DB
    connection has been observed to drop under long-held connections)."""
    if graph != DEFAULT_GRAPH:
        raise ValueError(f"run_chunk() only writes to {DEFAULT_GRAPH!r}, got graph={graph!r}")
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT * FROM cypher('{graph}', $$ {query} $$, %s::agtype) AS (v agtype);",
            (json.dumps({"rows": rows}),),
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
    """Read-only helper: run a MATCH...RETURN query against `graph` (any graph,
    including quran_kg/hadith_kg) and decode the agtype columns named in
    `columns` (order must match the Cypher RETURN order). Returns list[dict].

    `desc` is printed before the query runs and the fetched row count is
    printed right after -- the query itself gives zero feedback while it's
    running (a big MATCH...RETURN can take minutes), so this is the only way
    to see it's not stuck."""
    if desc:
        print(f"  membaca {desc} dari {graph}...", flush=True)
    col_sql = ", ".join(f"{c} agtype" for c in columns)
    with conn.cursor() as cur:
        cur.execute(f"SELECT * FROM cypher('{graph}', $$ {query} $$) AS ({col_sql});")
        rows = cur.fetchall()
    if desc:
        print(f"    -> {len(rows):,} baris, decoding...", flush=True)
    result = [
        {col: _decode(val) for col, val in zip(columns, row)}
        for row in tqdm(rows, unit="row", desc=f"  decode {desc}" if desc else "decode", leave=False)
    ]
    return result


def count(conn, graph, query):
    with conn.cursor() as cur:
        cur.execute(f"SELECT * FROM cypher('{graph}', $$ {query} $$) AS (v agtype);")
        return int(str(cur.fetchone()[0]))
