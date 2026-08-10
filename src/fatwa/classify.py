"""
Klasifikasi sitasi footnote + normalisasi kunci join. Port verbatim dari
`fatwa_hadith_linking_experiment.ipynb` / `fatwa_quran_linking_experiment.ipynb`
(logikanya identik di kedua notebook itu).
"""
import re

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

COLLECTIONS = {
    "البخاري": "Bukhari", "مسلم": "Muslim", "الترمذي": "Tirmizi",
    "أبو داود": "AbuDaud", "أبي داود": "AbuDaud",
    "النسائي": "Nesai", "ابن ماجه": "IbnMaja",
}
NOT_IN_CORPUS_KW = ["أحمد", "الدارمي", "مالك", "موطأ"]
NUM_PATTERN = re.compile(r"\(([٠-٩\d\s/\-–]+)\)")

QURAN_REF = re.compile(r"سورة\s+([؀-ۿ]+(?:\s+[؀-ۿ]+){0,2}?)\s+الآية\s+([٠-٩]+)")
ALEF_VARIANTS = re.compile(r"[إأآا]")


def to_int(s):
    return int(s.translate(ARABIC_DIGITS))


def norm_alef(s):
    return ALEF_VARIANTS.sub("ا", s)


def normalize_nomor(x):
    """~15% node Hadith di islamic_kg simpan nomor dgn akhiran ".0" (mis.
    "8.0"), sisanya tanpa ("3188") -- bug format dari stringifikasi pandas
    float saat load. Wajib dinormalisasi kedua sisi sebelum join, kalau
    tidak match valid akan salah kebaca "no_match"."""
    s = str(x).strip()
    if s.endswith(".0"):
        s = s[:-2]
    try:
        return str(int(float(s)))
    except ValueError:
        return s


def split_citations(entry_text):
    return [c.strip() for c in re.split(r"،|,", entry_text) if c.strip()]


def classify_citation(c):
    if "سورة" in c:
        return "quran", None, None
    matched_col = next((col for kw, col in COLLECTIONS.items() if kw in c), None)
    not_in_corpus = any(kw in c for kw in NOT_IN_CORPUS_KW)
    if matched_col or not_in_corpus or "متفق عليه" in c:
        m = NUM_PATTERN.search(c)
        num = None
        if m:
            raw = m.group(1)
            if "/" not in raw and "-" not in raw and "–" not in raw:
                digits = raw.translate(ARABIC_DIGITS).strip()
                if digits.isdigit():
                    num = int(digits)
        if num is not None and matched_col:
            return "hadith_with_number", matched_col, num
        return "hadith_no_number", matched_col, None
    return "other", None, None


def parse_quran_citation(text):
    """Return (surah_name_raw, ayah_num) atau (None, None) kalau regex tidak cocok."""
    m = QURAN_REF.search(text)
    if not m:
        return None, None
    return m.group(1).strip(), to_int(m.group(2))
