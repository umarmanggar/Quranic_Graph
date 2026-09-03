"""
Konstanta terpusat untuk pipeline `isSimilar` (kemiripan teks Arab lintas &
sesama sumber). Semua modul lain di folder ini meng-import dari sini supaya
tuning (threshold, ukuran chunk, budget batch) cukup diubah di satu tempat.
"""
import os
from pathlib import Path

# --- OpenAI embedding ---------------------------------------------------------
MODEL = "text-embedding-3-small"
EMBED_DIMS = 1536            # text-embedding-3-small mendukung 512/1536; 512 = hemat memori & index 3x
EMBED_BATCH_TOKENS = 100_000  # anggaran token per request (di bawah limit request embeddings OpenAI)
EMBED_BATCH_ITEMS = 2048      # limit jumlah input per request embeddings OpenAI
EMBED_CONCURRENCY = 3         # request paralel (cukup utk tutupi latensi jaringan; throttling di RateLimiter)
EMBED_MAX_RETRIES = 8
# Rate limit organisasi OpenAI (tokens-per-minute). Cek nilai asli di
# platform.openai.com/settings/organization/limits -- naikkan kalau tier sudah naik.
TPM_LIMIT = 1_000_000
TPM_HEADROOM = 0.85          # target pemakaian = TPM_LIMIT * ini (sisakan ruang utk drift hitung token)

# --- chunking ---------------------------------------------------------------
TIKTOKEN_ENCODING = "cl100k_base"
CHUNK_TOKENS = 256
CHUNK_OVERLAP = 48
MAX_CHUNKS_PER_DOC = 256      # batas untuk node Fatwa "garbage dump" (~300-400rb char)

# --- similarity / search --------------------------------------------------
THRESHOLD = 0.80             # dipakai edges.py; setel ulang setelah calibrate.py
SEARCH_FLOOR = 0.70          # simpan pair di atas ini di pairs.parquet (headroom kalibrasi)
TOP_K = 64                   # tetangga per chunk saat query FAISS
QUERY_BATCH = 4096           # chunk per iterasi index.search()
FAISS_INDEX = "auto"        # "auto" | "flat" | "hnsw"
FAISS_FLAT_MAX_VECTORS = 500_000  # di atas ini "auto" pindah ke HNSW
HNSW_M = 32
HNSW_EF_SEARCH = 128

# --- bentuk edge ----------------------------------------------------------
# Arah edge deterministik: node dgn prioritas label lebih kecil jadi source;
# kalau label sama, node_key yang lebih kecil (string) jadi source.
LABEL_PRIORITY = ["Ayah", "Tafsir", "Hadith", "Fatwa"]
EDGE_LABEL = "isSimilar"

# --- sumber node di islamic_kg -----------------------------------------------
# (label, prop key unik, prop teks Arab)
NODE_SPECS = [
    ("Ayah", "verse_key", "text_arabic"),
    ("Hadith", "hadith_id", "arabic_matn"),
    ("Tafsir", "tafsir_id", "text_arabic"),
    ("Fatwa", "fatwa_id", "text_arabic"),
]
KEY_PROP = {label: key for label, key, _ in NODE_SPECS}

# Tipe prop key di islamic_kg: hadith_id disimpan sebagai INTEGER (agtype number),
# sisanya string (verse_key "2:255", tafsir_id "as_saadi:1:1", fatwa_id "...:181").
# Artefak parquet menyimpan semua key sebagai string; edges.py cast balik pakai ini
# sebelum MATCH -- kalau tidak, MATCH (h:Hadith {hadith_id: "4626"}) tidak ketemu
# apa-apa dan semua edge Hadith gagal dibuat tanpa error.
KEY_CAST = {"Hadith": int}

# --- path artefak -----------------------------------------------------------
CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "similarity"
DOCS_PARQUET = CACHE_DIR / "docs.parquet"
CHUNKS_PARQUET = CACHE_DIR / "chunks.parquet"
EMBED_DIR = CACHE_DIR / "embeddings"       # berisi part-*.parquet (chunk_uid, vector)
PAIRS_PARQUET = CACHE_DIR / "pairs.parquet"
CALIBRATION_CSV = CACHE_DIR / "calibration_sample.csv"

# --- dry-run subset -------------------------------------------------------
# SIM_SUBSET=1 -> fetch.py hanya ambil sebagian kecil node tiap label (uji cepat,
# biaya embedding < 1 sen). Lihat fetch.SUBSET_LIMITS.
SUBSET = os.environ.get("SIM_SUBSET", "") not in ("", "0", "false", "False")
