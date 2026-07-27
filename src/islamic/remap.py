"""
Helper dipakai oleh wordoccurrence_*.py utk merekonstruksi peta old_id -> new_id
(Lemma/Root) dari state islamic_kg yang sudah ditulis lemma_root.py. Sengaja
dihitung ulang tiap kali (baca live graph), bukan lewat file handoff -- supaya
tiap modul tetap bisa dijalankan berdiri sendiri/idempotent (pola yang sama
dengan existing_lemmas() di tafsir/wordoccurrence.py).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import cypher_rows, DEFAULT_GRAPH
from ids import dedup_key


def islamic_lemma_key_to_id(conn):
    rows = cypher_rows(conn, DEFAULT_GRAPH, "MATCH (l:Lemma) RETURN l.lemma_id, l.text",
                        ["lemma_id", "text"], desc="Lemma (islamic_kg, utk remap)")
    return {dedup_key(r["text"]): r["lemma_id"] for r in rows}


def islamic_root_key_to_id(conn):
    rows = cypher_rows(conn, DEFAULT_GRAPH, "MATCH (r:Root) RETURN r.root_id, r.arabic_trilateral",
                        ["root_id", "arabic_trilateral"], desc="Root (islamic_kg, utk remap)")
    return {dedup_key(r["arabic_trilateral"]): r["root_id"] for r in rows}


def old_lemma_id_to_new(conn, source_graph, query, columns, id_col, text_col, lemma_key_to_id=None):
    """Baca (id, text) lemma dari `source_graph`, kembalikan {old_id: new_lemma_id}."""
    if lemma_key_to_id is None:
        lemma_key_to_id = islamic_lemma_key_to_id(conn)
    rows = cypher_rows(conn, source_graph, query, columns, desc=f"Lemma remap ({source_graph})")
    return {r[id_col]: lemma_key_to_id[dedup_key(r[text_col])] for r in rows}
