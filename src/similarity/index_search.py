"""
Bangun index FAISS atas semua vektor chunk, lalu cari tetangga tiap chunk dan
agregasi ke level PASANGAN NODE dgn MAX cosine antar semua pasangan chunk.

-> data/similarity/pairs.parquet
(src_label, src_key, tgt_label, tgt_key, score, src_chunk, tgt_chunk)

Efisiensi: ANN (bukan O(n^2) brute force), query berbatch, dict pair hanya
menampung pasangan >= SEARCH_FLOOR sehingga memori terkendali. Arah pasangan
sudah dinormalisasi di sini (prioritas label lalu node_key) supaya edges.py
tinggal MERGE.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd
import faiss
from tqdm import tqdm

from config import (
    CHUNKS_PARQUET, EMBED_DIR, PAIRS_PARQUET, EMBED_DIMS,
    FAISS_INDEX, FAISS_FLAT_MAX_VECTORS, HNSW_M, HNSW_EF_SEARCH,
    TOP_K, QUERY_BATCH, SEARCH_FLOOR, LABEL_PRIORITY,
)

PRIO = {lb: i for i, lb in enumerate(LABEL_PRIORITY)}


def load_vectors():
    """Gabung semua part embedding + join ke chunks.parquet. Returns
    (vecs float32 [N,dims], meta DataFrame [node_label, node_key, chunk_index])
    sejajar baris."""
    parts = sorted(EMBED_DIR.glob("part-*.parquet"))
    if not parts:
        raise RuntimeError(f"tidak ada part embedding di {EMBED_DIR} -- jalankan embed.py dulu")
    emb = pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)
    emb = emb.drop_duplicates(subset="chunk_uid", keep="last")

    chunks = pd.read_parquet(CHUNKS_PARQUET, columns=["chunk_uid", "node_label", "node_key", "chunk_index"])
    merged = chunks.merge(emb, on="chunk_uid", how="inner")
    missing = len(chunks) - len(merged)
    if missing:
        print(f"  WARNING: {missing:,} chunk belum punya embedding, diabaikan")

    vecs = np.frombuffer(b"".join(merged["vector"].to_numpy()), dtype=np.float32)
    vecs = vecs.reshape(len(merged), EMBED_DIMS).copy()
    meta = merged[["node_label", "node_key", "chunk_index"]].reset_index(drop=True)
    return vecs, meta


def build_index(vecs):
    n, d = vecs.shape
    kind = FAISS_INDEX
    if kind == "auto":
        kind = "flat" if n <= FAISS_FLAT_MAX_VECTORS else "hnsw"
    print(f"  index FAISS: {kind} atas {n:,} vektor dim {d}")
    if kind == "flat":
        idx = faiss.IndexFlatIP(d)
    else:
        # 2-arg ctor + set metric -> portabel lintas versi faiss (vektor sudah
        # L2-normalized dari embed.py, jadi inner product == cosine)
        idx = faiss.IndexHNSWFlat(d, HNSW_M)
        idx.metric_type = faiss.METRIC_INNER_PRODUCT
        idx.hnsw.efSearch = HNSW_EF_SEARCH
    idx.add(vecs)
    return idx


def ordered_pair(la, ka, ca, lb, kb, cb):
    """(src, tgt) sesuai prioritas label lalu node_key. Returns
    (src_label, src_key, tgt_label, tgt_key, src_chunk, tgt_chunk) atau None utk self."""
    if la == lb and ka == kb:
        return None
    a = (PRIO[la], ka)
    b = (PRIO[lb], kb)
    if a <= b:
        return (la, ka, lb, kb, ca, cb)
    return (lb, kb, la, ka, cb, ca)


def main():
    vecs, meta = load_vectors()
    labels = meta["node_label"].to_numpy()
    keys = meta["node_key"].to_numpy()
    cidx = meta["chunk_index"].to_numpy()

    index = build_index(vecs)

    best = {}   # (src_label, src_key, tgt_label, tgt_key) -> (score, src_chunk, tgt_chunk)
    n = len(vecs)
    for start in tqdm(range(0, n, QUERY_BATCH), unit="qbatch"):
        q = vecs[start:start + QUERY_BATCH]
        D, I = index.search(q, TOP_K + 1)   # +1: tetangga pertama biasanya diri sendiri
        for row in range(q.shape[0]):
            i = start + row
            for score, j in zip(D[row], I[row]):
                if j < 0 or j == i or score < SEARCH_FLOOR:
                    continue
                pair = ordered_pair(labels[i], keys[i], int(cidx[i]),
                                    labels[j], keys[j], int(cidx[j]))
                if pair is None:
                    continue
                sl, sk, tl, tk, sc, tc = pair
                k = (sl, sk, tl, tk)
                prev = best.get(k)
                if prev is None or score > prev[0]:
                    best[k] = (float(score), sc, tc)

    rows = [
        {"src_label": sl, "src_key": sk, "tgt_label": tl, "tgt_key": tk,
         "score": v[0], "src_chunk": v[1], "tgt_chunk": v[2]}
        for (sl, sk, tl, tk), v in best.items()
    ]
    df = pd.DataFrame(rows, columns=[
        "src_label", "src_key", "tgt_label", "tgt_key", "score", "src_chunk", "tgt_chunk"
    ]).sort_values("score", ascending=False).reset_index(drop=True)
    df.to_parquet(PAIRS_PARQUET, index=False)

    print(f"pairs.parquet: {len(df):,} pasangan node >= {SEARCH_FLOOR} -> {PAIRS_PARQUET}")
    if len(df):
        combo = (df["src_label"] + "-" + df["tgt_label"]).value_counts()
        for name, c in combo.items():
            print(f"  {name:16s}: {c:,}")


if __name__ == "__main__":
    main()
