import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import graph_connection, run_batch, sqlite_rows

CREATE = """
UNWIND $rows AS row
CREATE (:Surah {
  surah_id: row.surah_id,
  name_arabic: row.name_arabic,
  name_latin: row.name_latin,
  revelation_place: row.revelation_place,
  total_ayah: row.total_ayah
})
"""


def main():
    src = sqlite_rows(
        "al-quran/quran-metadata-surah-name.sqlite",
        "SELECT id, name_arabic, name_simple, revelation_place, verses_count FROM chapters",
    )
    rows = [{
        "surah_id": r["id"],
        "name_arabic": r["name_arabic"],
        "name_latin": r["name_simple"],
        "revelation_place": r["revelation_place"],
        "total_ayah": r["verses_count"],
    } for r in src]

    with graph_connection() as conn:
        run_batch(conn, CREATE, rows)
    print(f"Surah: {len(rows)} nodes")


if __name__ == "__main__":
    main()