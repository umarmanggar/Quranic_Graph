import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import graph_connection, run_batch, sqlite_rows

CREATE = """
UNWIND $rows AS row
MATCH (a:Ayah {verse_key: row.verse_key})
CREATE (a)-[:HAS_TRANSLATION]->(:Translation {language: row.language, source: row.source, text: row.text})
"""


def main():
    src = sqlite_rows("al-quran/quran-id-simple.db", "SELECT ayah_key, text FROM translation")
    rows = [{
        "verse_key": r["ayah_key"],
        "language": "id",
        "source": "Kemenag",
        "text": r["text"],
    } for r in src]

    with graph_connection() as conn:
        run_batch(conn, CREATE, rows)
    print(f"Translation: {len(rows)} nodes + HAS_TRANSLATION edges")


if __name__ == "__main__":
    main()