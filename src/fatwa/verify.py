"""
Verifikasi hasil pipeline fatwa. Angka EXPECTED_RELATED_* di bawah BUKAN
angka mentah dari notebook eksperimen (15.355 sitasi hadith / 7.223 sitasi
quran ter-resolve) -- itu angka di level SITASI, sedangkan edge di graph ini
di level (fatwa_id, target) UNIK: MERGE mendedup wajar kalau satu fatwa
mengutip hadits/ayat yang sama lewat >1 footnote berbeda (validasi run
pertama, 2026-08-09: hadith 15.355 sitasi resolved -> 14.126 edge unik;
quran 7.223 sitasi resolved -> 6.458 edge unik -- lihat resolve_rows() di
fatwa_hadith.py/fatwa_quran.py). Angka EXPECTED di sini diambil dari hasil
run pertama yang tervalidasi itu sbg baseline regresi, bukan dari notebook.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import graph_connection, count, DEFAULT_GRAPH

GRAPH = DEFAULT_GRAPH

EXPECTED_FATWA = 9902
EXPECTED_FATWA_WITH_FOOTNOTE = 4460
EXPECTED_RELATED_HADITH = 14126
EXPECTED_RELATED_QURAN = 6458


def flag(actual, expected, tolerance=0.1):
    if expected == 0:
        return ""
    diff = abs(actual - expected) / expected
    return "" if diff <= tolerance else f"  jauh dari ballpark notebook ({expected:,}) - cek kemungkinan bug"


def main():
    with graph_connection() as conn:
        n_fatwa = count(conn, GRAPH, "MATCH (f:Fatwa) RETURN count(*)")
        n_with_footnote = count(conn, GRAPH, "MATCH (f:Fatwa) WHERE f.n_footnotes > 0 RETURN count(*)")
        n_related_hadith = count(conn, GRAPH, "MATCH ()-[r:RELATED_HADITH]->() RETURN count(r)")
        n_related_quran = count(conn, GRAPH, "MATCH ()-[r:RELATED_QURAN]->() RETURN count(r)")

    print(f"Fatwa                 {n_fatwa:6}{flag(n_fatwa, EXPECTED_FATWA)}")
    print(f"  dgn >=1 footnote    {n_with_footnote:6}{flag(n_with_footnote, EXPECTED_FATWA_WITH_FOOTNOTE)}")
    print(f"RELATED_HADITH edges  {n_related_hadith:6}{flag(n_related_hadith, EXPECTED_RELATED_HADITH)}")
    print(f"RELATED_QURAN edges   {n_related_quran:6}{flag(n_related_quran, EXPECTED_RELATED_QURAN)}")


if __name__ == "__main__":
    main()
