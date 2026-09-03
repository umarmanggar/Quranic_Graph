"""
Potong tiap dokumen jadi chunk token (sliding window CHUNK_TOKENS / CHUNK_OVERLAP)
-> data/similarity/chunks.parquet
(chunk_uid, node_label, node_key, chunk_index, n_tokens, text).

Dokumen pendek -> 1 chunk. Dokumen sangat panjang (node Fatwa "garbage dump")
di-truncate di MAX_CHUNKS_PER_DOC dan dicatat.

chunk_uid = sha1(label \x1f key \x1f idx \x1f text) -> kunci cache stabil di embed.py
(re-run chunk.py tidak mengubah uid selama teks & param sama).
"""
import sys
import hashlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import tiktoken
from tqdm import tqdm

from config import (
    DOCS_PARQUET, CHUNKS_PARQUET, TIKTOKEN_ENCODING,
    CHUNK_TOKENS, CHUNK_OVERLAP, MAX_CHUNKS_PER_DOC,
)

STRIDE = CHUNK_TOKENS - CHUNK_OVERLAP
assert STRIDE > 0, "CHUNK_OVERLAP harus < CHUNK_TOKENS"


def _uid(label, key, idx, text):
    h = hashlib.sha1()
    h.update(f"{label}\x1f{key}\x1f{idx}\x1f{text}".encode("utf-8"))
    return h.hexdigest()


def chunk_tokens(tok, text):
    ids = tok.encode(text)
    if len(ids) <= CHUNK_TOKENS:
        return [(ids, text)]
    out = []
    for start in range(0, len(ids), STRIDE):
        piece = ids[start:start + CHUNK_TOKENS]
        if not piece:
            break
        out.append((piece, tok.decode(piece)))
        if start + CHUNK_TOKENS >= len(ids):
            break
    return out


def main():
    tok = tiktoken.get_encoding(TIKTOKEN_ENCODING)
    docs = pd.read_parquet(DOCS_PARQUET)

    records, truncated = [], 0
    for d in tqdm(docs.itertuples(index=False), total=len(docs), unit="doc"):
        pieces = chunk_tokens(tok, d.text)
        if len(pieces) > MAX_CHUNKS_PER_DOC:
            pieces = pieces[:MAX_CHUNKS_PER_DOC]
            truncated += 1
        for idx, (ids, ptext) in enumerate(pieces):
            records.append({
                "chunk_uid": _uid(d.node_label, d.node_key, idx, ptext),
                "node_label": d.node_label,
                "node_key": d.node_key,
                "chunk_index": idx,
                "n_tokens": len(ids),
                "text": ptext,
            })

    df = pd.DataFrame(records)
    df = df.drop_duplicates(subset="chunk_uid").reset_index(drop=True)
    df.to_parquet(CHUNKS_PARQUET, index=False)

    per_doc = df.groupby(["node_label", "node_key"]).size()
    print(f"chunks.parquet: {len(df):,} chunk dari {len(docs):,} dokumen "
          f"(rata-rata {per_doc.mean():.1f}/dok, maks {per_doc.max()})")
    print(f"  {truncated:,} dokumen di-truncate di {MAX_CHUNKS_PER_DOC} chunk")
    print(f"  total token ~{df['n_tokens'].sum():,} (estimasi biaya embedding "
          f"~US${df['n_tokens'].sum() / 1_000_000 * 0.02:.2f})")


if __name__ == "__main__":
    main()
