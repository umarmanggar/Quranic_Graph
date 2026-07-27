"""
Normalisasi teks Arab untuk dedup key Lemma/Root lintas quran_kg/hadith_kg.
Dicek langsung ke DB: teks Lemma quran_kg berharakat penuh, TafsirLemma/hadith
nyaris tanpa harakat -- overlap teks apa adanya ~0%, setelah normalisasi ini
naik ke ~60-70%. Field `text` yang disimpan tetap ejaan asli (lihat lemma_root.py),
normalize_key/dedup_key HANYA dipakai sebagai kunci pencocokan.
"""
import re

DIACRITICS = re.compile(r"[ً-ٰٟۖ-ۭ]")
TATWEEL = "ـ"

ALEF_VARIANTS = str.maketrans({
    "إ": "ا",  # إ -> ا
    "أ": "ا",  # أ -> ا
    "آ": "ا",  # آ -> ا
})
YA_TA_VARIANTS = str.maketrans({
    "ى": "ي",  # ى (alef maksura) -> ي
    "ة": "ه",  # ة (ta marbuta) -> ه
})

HOMONYM_SUFFIX = re.compile(r"[0-9]+$")


def normalize_key(text):
    if text is None:
        return None
    t = DIACRITICS.sub("", text)
    t = t.replace(TATWEEL, "")
    t = t.translate(ALEF_VARIANTS)
    t = t.translate(YA_TA_VARIANTS)
    return t.strip()


def strip_homonym_suffix(text):
    """hadith_kg Lemma pakai akhiran angka utk beda makna homonim (mis. "خَارَ1"
    vs "خَارَ2"). Dibuang di sini karena user pilih dedup maksimal (lihat plan)."""
    return HOMONYM_SUFFIX.sub("", text) if text else text


def dedup_key(text):
    return normalize_key(strip_homonym_suffix(text))
