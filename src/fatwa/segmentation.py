"""
Segmentasi halaman Fatawa Lajnah Daimah (level `body`/`footnotes` per halaman)
jadi fatwa individual. Port dari
`Kitab Lajnah Daiman Majumah/footnote_descriptive_stats.ipynb` Bagian 2, dgn
satu tambahan: selain menghitung & mengatribusi footnote entries per fatwa,
`segment_book()` di sini juga mengumpulkan potongan teks `body` per fatwa
(fatwa_text) supaya Fatwa node bisa menyimpan teks lengkap.

Setiap step (fatwa.py/fatwa_hadith.py/fatwa_quran.py) memanggil
segment_all_books() sendiri-sendiri (bukan baca dari artifact perantara) --
konsisten dgn pola modul lain di repo ini yang independently re-runnable
(mis. tafsir/wordoccurrence.py me-lemmatize ulang tiap run).

Gotcha yang wajib dipertahankan (lihat notebook sumber utk detail lengkap):
- Marker footnote `(N)`/`(¬N)` reset PER HALAMAN, bukan per buku -- tidak
  bisa di-join lewat angka, harus lewat urutan kemunculan.
- Angka `(N)` yang jadi bagian heading "...فتوى رقم (N)" itu sendiri BUKAN
  sitasi footnote -- exclude_spans mengecualikannya dari perhitungan marker.
- `فتوى رقم (N)` bisa berupa heading fatwa baru ATAU sitasi silang ke fatwa
  lain di tengah kalimat -- FATWA_START membedakan lewat kata pembuka
  formulaik (`س`/`الحمد`/`فقد`/`السؤال`) setelah nomornya.
"""
import re
import sys
import itertools
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

from db import DATA_DIR

BOOK_IDS = ["lajnah_daimah_majmuah1", "lajnah_daimah_majmuah2"]

FATWA_START = re.compile(
    r"(?:السؤال(?:ان)?\s+.+?\s+من\s+)?(?:ال)?فتوى\s+رقم\s*\(([٠-٩]+)\)"
    r"\s*(?:\(¬?[٠-٩]+\)\s*)?:?\s*(?:س|الحمد|فقد|السؤال)"
)
INLINE_MARKER = re.compile(r"\(¬?([٠-٩]+)\)")
FOOTNOTE_ENTRY = re.compile(r"^\(¬?[٠-٩]+\)\s*(.*)", re.DOTALL)

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def to_int(s):
    return int(s.translate(ARABIC_DIGITS))


def read_pages(book_id):
    df = pd.read_parquet(DATA_DIR / "fatwa" / f"{book_id}_pages.parquet")
    return df.sort_values("sequence_num").reset_index(drop=True)


def split_footnote_entries(footnote_text):
    if not isinstance(footnote_text, str) or not footnote_text.strip():
        return []
    entries = []
    for line in footnote_text.split("\r"):
        line = line.strip()
        if not line:
            continue
        m = FOOTNOTE_ENTRY.match(line)
        entries.append(m.group(1).strip() if m else line)
    return entries


def count_markers(body, seg_start, seg_end, exclude_spans):
    count = 0
    for m in INLINE_MARKER.finditer(body, seg_start, seg_end):
        if any(es <= m.start() and m.end() <= ee for es, ee in exclude_spans):
            continue
        count += 1
    return count


def segment_book(df):
    """Return dict fatwa_number -> {"footnotes": [...], "text_parts": [...]},
    plus fatwa_order (urutan kemunculan) dan marker_mismatch_pages (ukuran
    reliabilitas heuristik, lihat notebook sumber)."""
    fatwas = {}
    fatwa_order = []
    current_fatwa = None
    marker_mismatch_pages = 0

    for _, row in df.iterrows():
        body = row["body"] or ""
        entries = split_footnote_entries(row["footnotes"])
        entry_iter = iter(entries)

        starts = list(FATWA_START.finditer(body))
        exclude_spans = [(m.start(1) - 1, m.end(1) + 1) for m in starts]

        segments = []
        if not starts:
            segments.append((0, len(body), current_fatwa))
        else:
            if starts[0].start() > 0:
                segments.append((0, starts[0].start(), current_fatwa))
            for i, m in enumerate(starts):
                seg_start = m.start()
                seg_end = starts[i + 1].start() if i + 1 < len(starts) else len(body)
                fnum = to_int(m.group(1))
                segments.append((seg_start, seg_end, fnum))
                current_fatwa = fnum
                if fnum not in fatwas:
                    fatwas[fnum] = {"footnotes": [], "text_parts": []}
                    fatwa_order.append(fnum)

        total_markers_on_page = 0
        for seg_start, seg_end, fnum in segments:
            n_markers = count_markers(body, seg_start, seg_end, exclude_spans)
            total_markers_on_page += n_markers
            assigned = list(itertools.islice(entry_iter, n_markers))
            if fnum is None:
                continue
            fatwas[fnum]["footnotes"].extend(assigned)
            seg_text = body[seg_start:seg_end].strip()
            if seg_text:
                fatwas[fnum]["text_parts"].append(seg_text)

        if total_markers_on_page != len(entries):
            marker_mismatch_pages += 1

    return fatwas, fatwa_order, marker_mismatch_pages


def segment_all_books():
    """List of dicts, one per fatwa across both books:
    {fatwa_id, book, fatwa_number, text_arabic, footnote_entries, n_footnotes}."""
    records = []
    for book_id in BOOK_IDS:
        df = read_pages(book_id)
        fatwas, fatwa_order, _ = segment_book(df)
        for fnum in fatwa_order:
            data = fatwas[fnum]
            records.append({
                "fatwa_id": f"{book_id}:{fnum}",
                "book": book_id,
                "fatwa_number": fnum,
                "text_arabic": "\n".join(data["text_parts"]),
                "footnote_entries": data["footnotes"],
                "n_footnotes": len(data["footnotes"]),
            })
    return records
