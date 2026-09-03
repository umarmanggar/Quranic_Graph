"""
Embedding chunk lewat OpenAI text-embedding-3-small -> data/similarity/embeddings/part-*.parquet
(chunk_uid, vector) dgn vector = float32 L2-normalized (cosine = inner product).

Efisiensi & ketahanan:
- resumable / checkpoint per-batch: chunk yang chunk_uid-nya sudah ada di part
  manapun di-skip. Kill di tengah lalu re-run = lanjut dari sisa, tidak dobel
  (tiap batch ditulis ke part-nya sendiri begitu selesai).
- rate limit: RateLimiter menjaga total token/menit di bawah TPM_LIMIT*TPM_HEADROOM
  (rolling window 60 dtk), jadi tidak membanjiri API sampai kena 429 beruntun.
  Kalau 429 tetap lolos, tunggu sesuai hint "try again in Xs" dari server.
- batch kecil (EMBED_BATCH_TOKENS) supaya throttling halus & retry murah.

Butuh env OPENAI_API_KEY.
"""
import sys
import re
import time
import random
import threading
from collections import deque
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd
from tqdm import tqdm
from openai import OpenAI, RateLimitError

from config import (
    CHUNKS_PARQUET, EMBED_DIR, MODEL, EMBED_DIMS,
    EMBED_BATCH_TOKENS, EMBED_BATCH_ITEMS, EMBED_CONCURRENCY, EMBED_MAX_RETRIES,
    TPM_LIMIT, TPM_HEADROOM,
)

# max_retries=0: kendali retry sepenuhnya di loop kita (biar tidak dobel tunggu
# dgn retry internal SDK yang tidak tahu soal RateLimiter di bawah).
client = OpenAI(max_retries=0)

_HINT = re.compile(r"try again in ([\d.]+)s")


def retry_hint(exc):
    m = _HINT.search(str(exc))
    return float(m.group(1)) if m else None


class RateLimiter:
    """Token-bucket rolling-window: batasi jumlah token yang 'dikirim' dalam 60
    detik terakhir supaya <= cap. Thread-safe (dipakai dari beberapa worker)."""

    def __init__(self, cap_per_min):
        self.cap = max(1, int(cap_per_min))
        self.events = deque()   # (monotonic_ts, tokens)
        self.used = 0
        self.lock = threading.Lock()

    def acquire(self, tokens):
        while True:
            with self.lock:
                now = time.monotonic()
                while self.events and now - self.events[0][0] >= 60:
                    self.used -= self.events.popleft()[1]
                if not self.events or self.used + tokens <= self.cap:
                    self.events.append((now, tokens))
                    self.used += tokens
                    return
                wait = 60 - (now - self.events[0][0]) + 0.05
            time.sleep(min(wait, 5))


limiter = RateLimiter(TPM_LIMIT * TPM_HEADROOM)


def seen_uids():
    if not EMBED_DIR.exists():
        return set()
    seen = set()
    for part in EMBED_DIR.glob("part-*.parquet"):
        seen.update(pd.read_parquet(part, columns=["chunk_uid"])["chunk_uid"].tolist())
    return seen


def pack_batches(rows):
    """rows: list[(chunk_uid, text, n_tokens)] -> list[list[row]] sesuai budget."""
    batches, cur, cur_tok = [], [], 0
    for r in rows:
        n = min(r[2], EMBED_BATCH_TOKENS)
        if cur and (cur_tok + n > EMBED_BATCH_TOKENS or len(cur) >= EMBED_BATCH_ITEMS):
            batches.append(cur)
            cur, cur_tok = [], 0
        cur.append(r)
        cur_tok += n
    if cur:
        batches.append(cur)
    return batches


def embed_batch(texts, n_tokens):
    for attempt in range(1, EMBED_MAX_RETRIES + 1):
        limiter.acquire(n_tokens)
        try:
            resp = client.embeddings.create(model=MODEL, input=texts, dimensions=EMBED_DIMS)
            return [d.embedding for d in resp.data]
        except RateLimitError as e:
            if attempt == EMBED_MAX_RETRIES:
                raise
            wait = (retry_hint(e) or min(2 ** attempt, 60)) + random.uniform(0.5, 1.5)
            time.sleep(wait)
        except Exception as e:
            if attempt == EMBED_MAX_RETRIES:
                raise
            wait = min(2 ** attempt, 60) + random.uniform(0, 1)
            print(f"\n  embed batch gagal (attempt {attempt}/{EMBED_MAX_RETRIES}): {e!r} -- retry dlm {wait:.1f}s")
            time.sleep(wait)


def write_part(run_id, seq, uids, vectors):
    arr = np.asarray(vectors, dtype=np.float32)
    arr /= np.linalg.norm(arr, axis=1, keepdims=True).clip(min=1e-12)
    df = pd.DataFrame({"chunk_uid": uids, "vector": [v.tobytes() for v in arr]})
    df.to_parquet(EMBED_DIR / f"part-{run_id}-{seq:05d}.parquet", index=False)


def main():
    EMBED_DIR.mkdir(parents=True, exist_ok=True)
    chunks = pd.read_parquet(CHUNKS_PARQUET, columns=["chunk_uid", "text", "n_tokens"])
    done = seen_uids()
    todo = [
        (r.chunk_uid, r.text, int(r.n_tokens))
        for r in chunks.itertuples(index=False) if r.chunk_uid not in done
    ]
    print(f"embed: {len(chunks):,} chunk total, {len(done):,} sudah ada, {len(todo):,} akan di-embed")
    if not todo:
        print("  tidak ada yang perlu di-embed.")
        return

    batches = pack_batches(todo)
    total_tok = sum(r[2] for r in todo)
    run_id = time.strftime("%Y%m%d-%H%M%S")
    eta_min = total_tok / (TPM_LIMIT * TPM_HEADROOM)
    print(f"  {len(batches)} batch, konkuren {EMBED_CONCURRENCY}, model {MODEL} dim {EMBED_DIMS}")
    print(f"  ~{total_tok:,} token, target <= {int(TPM_LIMIT * TPM_HEADROOM):,} tpm -> ETA >= {eta_min:.0f} menit")

    with ThreadPoolExecutor(max_workers=EMBED_CONCURRENCY) as ex:
        futs = {
            ex.submit(embed_batch, [r[1] for r in b], sum(r[2] for r in b)): (seq, b)
            for seq, b in enumerate(batches)
        }
        for fut in tqdm(as_completed(futs), total=len(futs), unit="batch"):
            seq, b = futs[fut]
            vectors = fut.result()
            write_part(run_id, seq, [r[0] for r in b], vectors)

    total_parts = len(list(EMBED_DIR.glob("part-*.parquet")))
    print(f"selesai: {len(todo):,} vektor baru ditulis, {total_parts} part total di {EMBED_DIR}")


if __name__ == "__main__":
    main()
