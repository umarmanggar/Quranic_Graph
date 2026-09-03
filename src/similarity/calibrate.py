"""
Bantu memilih THRESHOLD final (dijalankan MANUAL, di antara index_search.py dan
edges.py -- tidak masuk STEPS default).

Dari pairs.parquet: cetak histogram skor (total + per kombinasi label), lalu
ambil sampel acak per band skor, gabung kembali teks aslinya dari docs.parquet,
tulis calibration_sample.csv untuk ditinjau. Setel config.THRESHOLD setelahnya.

    python calibrate.py            # 40 sampel per band
    python calibrate.py 80         # 80 sampel per band
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

from config import PAIRS_PARQUET, DOCS_PARQUET, CALIBRATION_CSV, SEARCH_FLOOR

BANDS = [(0.70, 0.75), (0.75, 0.80), (0.80, 0.85), (0.85, 0.90), (0.90, 0.95), (0.95, 1.01)]
SNIPPET = 300


def main():
    per_band = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    pairs = pd.read_parquet(PAIRS_PARQUET)
    docs = pd.read_parquet(DOCS_PARQUET)
    text_of = {(r.node_label, r.node_key): r.text for r in docs.itertuples(index=False)}

    print(f"== histogram skor ({len(pairs):,} pasangan >= {SEARCH_FLOOR}) ==")
    for lo, hi in BANDS:
        m = pairs[(pairs.score >= lo) & (pairs.score < hi)]
        print(f"  [{lo:.2f}, {hi:.2f}) : {len(m):,}")
    print("== per kombinasi label (semua band) ==")
    combo = (pairs.src_label + "-" + pairs.tgt_label).value_counts()
    for name, c in combo.items():
        print(f"  {name:16s}: {c:,}")

    sample = []
    for lo, hi in BANDS:
        m = pairs[(pairs.score >= lo) & (pairs.score < hi)]
        if len(m):
            sample.append(m.sample(min(per_band, len(m)), random_state=0))
    sample = pd.concat(sample, ignore_index=True) if sample else pairs.head(0)

    sample["src_text"] = [text_of.get((r.src_label, r.src_key), "")[:SNIPPET] for r in sample.itertuples(index=False)]
    sample["tgt_text"] = [text_of.get((r.tgt_label, r.tgt_key), "")[:SNIPPET] for r in sample.itertuples(index=False)]
    sample = sample[[
        "score", "src_label", "src_key", "src_text", "tgt_label", "tgt_key", "tgt_text"
    ]].sort_values("score", ascending=False)
    sample.to_csv(CALIBRATION_CSV, index=False, encoding="utf-8-sig")
    print(f"\ncalibration_sample.csv: {len(sample):,} baris -> {CALIBRATION_CSV}")
    print("Tinjau manual, lalu setel config.THRESHOLD.")


if __name__ == "__main__":
    main()
