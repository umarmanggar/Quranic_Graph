"""
Buat edge :isSimilar di islamic_kg dari pairs.parquet yang score >= config.THRESHOLD.

Arah edge sudah dinormalisasi di index_search.py (prioritas label lalu node_key),
jadi di sini tinggal MATCH kedua ujung + MERGE. Karena tiap label punya nama
prop key berbeda (verse_key / hadith_id / tafsir_id / fatwa_id), baris dipisah
per kombinasi (src_label, tgt_label) dan tiap kombinasi pakai template Cypher
spesifik (lebih cepat & tak ambigu daripada filter label()).

Properti edge: score, model, method, chunk_tokens, src_chunk, tgt_chunk.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

from db import graph_connection, run_batch
from config import PAIRS_PARQUET, THRESHOLD, EDGE_LABEL, KEY_PROP, KEY_CAST, MODEL, CHUNK_TOKENS


def cast_key(label, key):
    """Artefak parquet simpan semua node_key sbg string; balikkan ke tipe asli
    di graph (mis. hadith_id INTEGER) sebelum MATCH."""
    fn = KEY_CAST.get(label)
    return fn(key) if fn else key


def template(src_label, tgt_label):
    return f"""
UNWIND $rows AS row
MATCH (a:{src_label} {{{KEY_PROP[src_label]}: row.src_key}})
MATCH (b:{tgt_label} {{{KEY_PROP[tgt_label]}: row.tgt_key}})
MERGE (a)-[r:{EDGE_LABEL}]->(b)
SET r.score = row.score, r.model = '{MODEL}', r.method = 'max_chunk_cosine',
    r.chunk_tokens = {CHUNK_TOKENS}, r.src_chunk = row.src_chunk, r.tgt_chunk = row.tgt_chunk
"""


def main():
    pairs = pd.read_parquet(PAIRS_PARQUET)
    keep = pairs[pairs.score >= THRESHOLD].copy()
    print(f"edges: {len(keep):,} / {len(pairs):,} pasangan >= THRESHOLD {THRESHOLD}")
    if keep.empty:
        print("  tidak ada edge dibuat.")
        return

    with graph_connection() as conn:
        for (sl, tl), grp in keep.groupby(["src_label", "tgt_label"], sort=True):
            rows = [
                {"src_key": cast_key(sl, r.src_key), "tgt_key": cast_key(tl, r.tgt_key),
                 "score": round(float(r.score), 6),
                 "src_chunk": int(r.src_chunk), "tgt_chunk": int(r.tgt_chunk)}
                for r in grp.itertuples(index=False)
            ]
            print(f"  {sl}-{tl}: {len(rows):,} edge", flush=True)
            run_batch(conn, template(sl, tl), rows)

    print(f"selesai: {len(keep):,} edge :{EDGE_LABEL} di-MERGE")


if __name__ == "__main__":
    main()
