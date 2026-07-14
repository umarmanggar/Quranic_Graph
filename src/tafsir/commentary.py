import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import re

from bs4 import BeautifulSoup

from db import graph_connection, run_batch, sqlite_rows

BRACE_NUM = re.compile(r"\{(\d+)\}")
WS = re.compile(r"\s+")

HEAD_ROW_QUERY = """
SELECT ayah_key, group_ayah_key, ayah_keys, text
FROM tafsir
WHERE ayah_key = group_ayah_key AND text IS NOT NULL AND TRIM(text) != ''
"""

CREATE_TAFSIR = """
UNWIND $rows AS row
CREATE (:Tafsir {
  tafsir_id: row.tafsir_id,
  text_arabic: row.text_arabic,
  text_indonesia: row.text_indonesia
})
"""

LINK_BOOK = """
UNWIND $rows AS row
MATCH (t:Tafsir {tafsir_id: row.tafsir_id})
MATCH (b:Book {book_id: row.book_id})
CREATE (t)-[:PART_OF_BOOK]->(b)
"""

LINK_AYAH = """
UNWIND $rows AS row
MATCH (t:Tafsir {tafsir_id: row.tafsir_id})
MATCH (a:Ayah {verse_key: row.verse_key})
CREATE (t)-[:INTERPRETS]->(a)
"""


def clean_html(raw_html):
    if not raw_html:
        return None
    text = BeautifulSoup(raw_html, "html.parser").get_text(separator=" ", strip=True)
    text = BRACE_NUM.sub("", text)
    text = text.replace("{", "").replace("}", "")
    return WS.sub(" ", text).strip() or None


def build_id_ayah_map(id_head_rows):
    mapping = {}
    for r in id_head_rows:
        cleaned = clean_html(r["text"])
        for k in (r["ayah_keys"] or "").split(","):
            if k:
                mapping[k] = (r["group_ayah_key"], cleaned)
    return mapping


def merge_indonesian_text(ar_ayah_keys, id_ayah_map):
    seen = {}
    for k in ar_ayah_keys:
        entry = id_ayah_map.get(k)
        if entry is None:
            continue
        gkey, text = entry
        if gkey not in seen:
            seen[gkey] = text
    parts = [t for t in seen.values() if t]
    return "\n\n".join(parts) if parts else None


def build_tafsir_rows():
    """Returns (tafsir_rows, ayah_links) built from the Arabic-canonical grouping."""
    ar_rows = sqlite_rows("tafsir/tafsir-as-saadi.db", HEAD_ROW_QUERY)
    id_rows = sqlite_rows("tafsir/id-tafsir-as-saadi.db", HEAD_ROW_QUERY)
    id_ayah_map = build_id_ayah_map(id_rows)

    tafsir_rows, ayah_links = [], []
    for r in ar_rows:
        tafsir_id = r["group_ayah_key"]
        ayah_keys = [k for k in (r["ayah_keys"] or "").split(",") if k]
        tafsir_rows.append({
            "tafsir_id": tafsir_id,
            "text_arabic": clean_html(r["text"]),
            "text_indonesia": merge_indonesian_text(ayah_keys, id_ayah_map),
        })
        for verse_key in ayah_keys:
            ayah_links.append({"tafsir_id": tafsir_id, "verse_key": verse_key})

    return tafsir_rows, ayah_links


def main():
    tafsir_rows, ayah_links = build_tafsir_rows()
    book_links = [{"tafsir_id": r["tafsir_id"], "book_id": "tafsir_as_saadi"} for r in tafsir_rows]

    with graph_connection() as conn:
        run_batch(conn, CREATE_TAFSIR, tafsir_rows)
        run_batch(conn, LINK_BOOK, book_links)
        run_batch(conn, LINK_AYAH, ayah_links)

    print(f"Tafsir: {len(tafsir_rows)} nodes + PART_OF_BOOK edges")
    print(f"INTERPRETS: {len(ayah_links)} edges")


if __name__ == "__main__":
    main()
