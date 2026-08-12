"""
Generate CSV kandidat RELATED_HADITH untuk Tafsir Ibnu Katsir.

Deteksi dari trigger ARAB (Ibnu Katsir tidak punya teks Indonesia):
- Trigger "maju" (qala rasul / qala nabi / an-nabi...qala): matan SESUDAH trigger
- Trigger "mundur" (rawahu / akhraja): matan SEBELUM trigger, mundur sampai
  penanda awal matan terdekat

Matan hadis dibaca dari node Hadith islamic_kg, dibersihkan DI MEMORI saat banding
(buang harakat + honorifik + sanad + komentar). Database TIDAK diubah.
Matan yang setelah dibersihkan < MIN_MATN_WORDS kata dibuang (rusak, sisa sanad).

Output CSV kandidat untuk review manual, BUKAN langsung edge.
Jalankan dari folder yang punya db.py (src/islamic).
    python ibnu_katsir_hadith_candidates.py
"""
import sys
import csv
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import graph_connection, cypher_rows
from rapidfuzz import fuzz, process

# ---------- konfigurasi ----------
BOOK_ID = "tafsir_ibnu_katsir"
THRESHOLD = 80          # ambang partial_ratio
TOP_K = 3               # kandidat per fragmen
MIN_FRAGMENT_WORDS = 5  # fragmen < ini dibuang
MIN_MATN_WORDS = 5      # matan hadis (setelah bersih) < ini dibuang (rusak)
OUT_CSV = "/home/umarmanggar/Projects/Quranic_Graph/data/tafsir/ibnu_katsir_hadith_candidates.csv"

# ---------- normalisasi + pembuangan frasa umum ----------
DIACRITICS = re.compile(r"[\u064B-\u0652\u0670\u0640]")  # harakat + tatwil

# honorifik & frasa doa yang muncul di hampir semua hadis -> buang biar tak jadi jangkar palsu
HONORIFIC = re.compile(
    r"صلى الله عليه وسلم|صلى اللّه عليه وسلم|"
    r"رضي الله عنه|رضي الله عنها|رضي الله عنهم|رضي الله عنهما|"
    r"عليه السلام|عليه الصلاة والسلام|"
    r"رحمه الله|عز وجل|تبارك وتعالى|سبحانه وتعالى|جل جلاله"
)

def normalize_ar(text):
    if not text:
        return ""
    text = HONORIFIC.sub(" ", text)          # buang honorifik dulu (sebelum harakat dilepas)
    text = DIACRITICS.sub("", text)
    text = HONORIFIC.sub(" ", text)          # sekali lagi tanpa harakat (jaga-jaga)
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ى", "ي").replace("ة", "ه")
    text = text.replace("ؤ", "و").replace("ئ", "ي").replace("ء", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text

# ---------- pembersih matan hadis (di memori) ----------
COMMENT_CUT = re.compile(r"(قال أبو عيسى|وفي الباب|قال أبو داود|رواه|أخرجه|هذا حديث).*$", re.DOTALL)
SANAD_CUT = re.compile(
    r".*?(?:قال رسول الله|قال النبي|عن النبي[^:]{0,30}?قال|أنه قال|يقول)\s*[:؛]?\s*",
    re.DOTALL,
)

def clean_matn(matn):
    """Buang komentar belakang + sanad depan, lalu normalisasi. Utk pembanding saja."""
    if not matn:
        return ""
    t = COMMENT_CUT.sub("", matn)
    m = SANAD_CUT.match(t)
    if m:
        t = t[m.end():]
    return normalize_ar(t)

# ---------- deteksi trigger + ekstraksi fragmen ----------
# Trigger MAJU: matan SESUDAH trigger
TRIGGERS_FWD = [
    ("QALA_RASUL", re.compile(r"قال رسول الله")),
    ("QALA_NABI",  re.compile(r"قال النبي")),
    ("AN_NABI_QALA", re.compile(r"عن النبي[^.﴿]{0,40}?قال")),
]
# Trigger MUNDUR: matan SEBELUM trigger
TRIGGERS_BWD = [
    ("RAWAHU",  re.compile(r"رواه")),
    ("AKHRAJA", re.compile(r"أخرجه")),
]
# batas AKHIR fragmen (arah maju berhenti di sini)
FWD_END = re.compile(r"(رواه|أخرجه|قال أبو|وفي الباب|هذا حديث|\.|﴿|»)")
# batas AWAL matan (arah mundur: mundur berhenti di penanda ini)
BWD_START = re.compile(r"(قال رسول الله|قال النبي|عن النبي|أنه قال|يقول|:|«|﴾)")
# kata2 khas takhrij -> kalau fragmen mengandung ini, kemungkinan besar bukan matan, buang
TAKHRIJ_NOISE = re.compile(r"(من طريق|من حديث|في مسنده|في سننه|في صحيحه|في معجمه|إسناد|رجاله|الحافظ|برقم)")

def extract_fragments(text):
    out = []
    # arah maju
    for label, trig in TRIGGERS_FWD:
        for m in trig.finditer(text):
            tail = text[m.end():m.end() + 400]
            end = FWD_END.search(tail)
            frag = tail[:end.start()] if end else tail
            frag = frag.strip(" :،.\"«»﴾﴿")
            if len(frag.split()) >= MIN_FRAGMENT_WORDS and not TAKHRIJ_NOISE.search(frag):
                out.append((label, frag))
    # arah mundur
    for label, trig in TRIGGERS_BWD:
        for m in trig.finditer(text):
            head = text[max(0, m.start() - 400):m.start()]
            starts = [mm.end() for mm in BWD_START.finditer(head)]
            frag = head[starts[-1]:] if starts else head
            frag = frag.strip(" :،.\"«»﴾﴿")
            if len(frag.split()) >= MIN_FRAGMENT_WORDS and not TAKHRIJ_NOISE.search(frag):
                out.append((label, frag))
    return out


def main():
    with graph_connection() as conn:
        tafsir_rows = cypher_rows(conn, "islamic_kg",
            f"MATCH (t:Tafsir {{book_id:'{BOOK_ID}'}}) RETURN t.tafsir_id, t.text_arabic",
            ["tafsir_id", "text_arabic"], desc="Tafsir Ibnu Katsir")

        hadith_rows = cypher_rows(conn, "islamic_kg",
            "MATCH (h:Hadith) RETURN h.hadith_id, h.nomor, h.grade, h.arabic_matn",
            ["hadith_id", "nomor", "grade", "arabic_matn"], desc="Hadith")

    print(f"  tafsir blok: {len(tafsir_rows)}, hadith: {len(hadith_rows)}", flush=True)

    # korpus hadis bersih; buang yang terlalu pendek (rusak / sisa sanad)
    hadith_clean, hadith_meta = [], []
    dropped_short = 0
    for h in hadith_rows:
        cleaned = clean_matn(h["arabic_matn"])
        if cleaned and len(cleaned.split()) >= MIN_MATN_WORDS:
            hadith_clean.append(cleaned)
            hadith_meta.append(h)
        else:
            dropped_short += 1
    print(f"  hadith siap-banding: {len(hadith_clean)} (dibuang krn pendek/rusak: {dropped_short})", flush=True)

    rows_out = []
    n_frag = 0
    for t in tafsir_rows:
        for label, frag in extract_fragments(t["text_arabic"] or ""):
            n_frag += 1
            frag_norm = normalize_ar(frag)
            if len(frag_norm.split()) < MIN_FRAGMENT_WORDS:
                continue
            matches = process.extract(frag_norm, hadith_clean,
                                      scorer=fuzz.partial_ratio, limit=TOP_K)
            for rank, (_, score, idx) in enumerate(matches, start=1):
                if score < THRESHOLD:
                    continue
                h = hadith_meta[idx]
                rows_out.append({
                    "tafsir_id": t["tafsir_id"], "trigger_label": label,
                    "fragment": frag, "rank": rank, "score": round(score, 1),
                    "hadith_id": h["hadith_id"], "nomor": h["nomor"], "grade": h["grade"],
                    "hadith_matn": h["arabic_matn"], "manual_label": "",
                })

    print(f"  fragmen terdeteksi: {n_frag}, kandidat lolos ambang {THRESHOLD}: {len(rows_out)}", flush=True)

    out_path = Path(OUT_CSV)
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "tafsir_id", "trigger_label", "fragment", "rank", "score",
            "hadith_id", "nomor", "grade", "hadith_matn", "manual_label"])
        writer.writeheader()
        writer.writerows(rows_out)

    print(f"CSV ditulis: {out_path} ({len(rows_out)} baris)")


if __name__ == "__main__":
    main()