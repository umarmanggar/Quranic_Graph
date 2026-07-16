import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import re
from collections import Counter

from bs4 import BeautifulSoup

from db import graph_connection, run_batch, sqlite_rows
from books import BOOKS

BRACE_NUM = re.compile(r"\{\s*[\d\u0660-\u0669\s\u0640\-\u2013,،]+\s*\}")
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
  book_id: row.book_id,
  text_arabic: row.text_arabic,
  text_indonesia: row.text_indonesia,
  text_english: row.text_english
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
    text = BRACE_NUM.sub(" ", text)
    return WS.sub(" ", text).strip() or None


def keys_of(row):
    return [k for k in (row["ayah_keys"] or "").split(",") if k]


def load_side(path):
    if not path:
        return {}
    rows = sqlite_rows(path, HEAD_ROW_QUERY)
    mapping = {}
    for r in rows:
        cleaned = clean_html(r["text"])
        for k in keys_of(r):
            mapping[k] = (r["group_ayah_key"], cleaned)
    return mapping


def merge_side(ar_keys, side_map, stats):
    seen = {}
    for k in ar_keys:
        entry = side_map.get(k)
        if entry is None:
            continue
        gkey, text = entry
        if gkey not in seen:
            seen[gkey] = text
    if not seen:
        stats["blocks_without_text"] += 1
        return None
    for gkey in seen:
        stats["pulled"][gkey] += 1
    if len(seen) > 1:
        stats["blocks_merging_multiple"] += 1
    parts = [t for t in seen.values() if t]
    return "\n\n".join(parts) if parts else None


def new_stats():
    return {"blocks_without_text": 0, "blocks_merging_multiple": 0, "pulled": Counter()}


def report(lang, stats, total):
    reused = sum(1 for v in stats["pulled"].values() if v > 1)
    print(
        f"  {lang:10} no_text={stats['blocks_without_text']:4}/{total}"
        f"  merged_multi={stats['blocks_merging_multiple']:4}"
        f"  source_blocks_reused={reused:4}"
    )


def build_tafsir_rows(book_id):
    cfg = BOOKS[book_id]
    prefix = cfg["prefix"]
    src = cfg["sources"]

    ar_rows = sqlite_rows(src["arabic"], HEAD_ROW_QUERY)
    id_map = load_side(src.get("indonesia"))
    en_map = load_side(src.get("english"))

    id_stats, en_stats = new_stats(), new_stats()
    tafsir_rows, ayah_links = [], []

    for r in ar_rows:
        tafsir_id = f"{prefix}:{r['group_ayah_key']}"
        ayah_keys = keys_of(r)
        tafsir_rows.append({
            "tafsir_id": tafsir_id,
            "book_id": book_id,
            "text_arabic": clean_html(r["text"]),
            "text_indonesia": merge_side(ayah_keys, id_map, id_stats) if id_map else None,
            "text_english": merge_side(ayah_keys, en_map, en_stats) if en_map else None,
        })
        for verse_key in ayah_keys:
            ayah_links.append({"tafsir_id": tafsir_id, "verse_key": verse_key})

    total = len(tafsir_rows)
    print(f"  arabic blocks={total}  ayah_links={len(ayah_links)}")
    if id_map:
        report("indonesia", id_stats, total)
    else:
        print("  indonesia  MISSING (no source)")
    if en_map:
        report("english", en_stats, total)
    else:
        print("  english    MISSING (no source)")

    return tafsir_rows, ayah_links


def main(book_id):
    tafsir_rows, ayah_links = build_tafsir_rows(book_id)
    book_links = [{"tafsir_id": r["tafsir_id"], "book_id": book_id} for r in tafsir_rows]

    with graph_connection() as conn:
        run_batch(conn, CREATE_TAFSIR, tafsir_rows)
        run_batch(conn, LINK_BOOK, book_links)
        run_batch(conn, LINK_AYAH, ayah_links)

    print(f"Tafsir: {len(tafsir_rows)} nodes, INTERPRETS: {len(ayah_links)} edges")