"""
Tarik teks Arab keempat sumber dari islamic_kg -> data/similarity/docs.parquet
(node_label, node_key, text). Baris teks kosong/None di-skip + dicatat.

SIM_SUBSET=1: hanya ambil sebagian kecil node tiap label (dry-run murah).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

from db import graph_connection, cypher_rows
from config import NODE_SPECS, CACHE_DIR, DOCS_PARQUET, SUBSET

SUBSET_LIMITS = {"Ayah": 250, "Hadith": 200, "Tafsir": 100, "Fatwa": 100}


def fetch_label(conn, label, key_prop, text_prop):
    limit = f" LIMIT {SUBSET_LIMITS[label]}" if SUBSET else ""
    rows = cypher_rows(
        conn, "islamic_kg",
        f"MATCH (n:{label}) RETURN n.{key_prop}, n.{text_prop}{limit}",
        ["node_key", "text"],
        desc=f"{label}.{text_prop}",
    )
    kept, empty = [], 0
    for r in rows:
        text = (r["text"] or "").strip()
        if not text:
            empty += 1
            continue
        kept.append({"node_label": label, "node_key": str(r["node_key"]), "text": text})
    print(f"  {label:8s}: {len(kept):,} dipakai, {empty:,} teks kosong di-skip")
    return kept


def main():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    all_rows = []
    with graph_connection() as conn:
        for label, key_prop, text_prop in NODE_SPECS:
            all_rows.extend(fetch_label(conn, label, key_prop, text_prop))

    df = pd.DataFrame(all_rows, columns=["node_label", "node_key", "text"])
    df.to_parquet(DOCS_PARQUET, index=False)
    print(f"docs.parquet: {len(df):,} dokumen -> {DOCS_PARQUET}"
          + ("  [SUBSET]" if SUBSET else ""))


if __name__ == "__main__":
    main()
