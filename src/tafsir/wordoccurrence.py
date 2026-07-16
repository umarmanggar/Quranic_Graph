import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import re
import json

import qalsadi.lemmatizer
from tqdm import tqdm

from db import graph_connection, run_batch, GRAPH
from commentary import build_tafsir_rows

TOKEN_TRIM = re.compile(r"^[\W\d]+|[\W\d]+$")

CREATE_WORD = """
UNWIND $rows AS row
MATCH (t:Tafsir {tafsir_id: row.tafsir_id})
CREATE (t)<-[:PART_OF_TAFSIR]-(:TafsirWordOccurrence {
  word_occurrence_id: row.word_occurrence_id,
  surface_form: row.surface_form,
  position_in_tafsir: row.position_in_tafsir
})
"""

CREATE_LEMMA = """
UNWIND $rows AS row
CREATE (:TafsirLemma {lemma_id: row.lemma_id, text: row.text})
"""

LINK_LEMMA = """
UNWIND $rows AS row
MATCH (w:TafsirWordOccurrence {word_occurrence_id: row.word_occurrence_id})
MATCH (l:TafsirLemma {lemma_id: row.lemma_id})
CREATE (w)-[:HAS_TAFSIR_LEMMA]->(l)
"""


def tokenize(text):
    tokens = []
    for raw in text.split():
        t = TOKEN_TRIM.sub("", raw)
        if t:
            tokens.append(t)
    return tokens


def existing_lemmas():
    with graph_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM cypher('{GRAPH}', $$ MATCH (l:TafsirLemma) "
                f"RETURN l.text, l.lemma_id $$) AS (t agtype, i agtype);"
            )
            return {json.loads(t): json.loads(i) for t, i in cur.fetchall()}


def next_index(lemma_ids):
    n = 0
    for lid in lemma_ids:
        if isinstance(lid, str) and lid.startswith("L") and lid[1:].isdigit():
            n = max(n, int(lid[1:]) + 1)
    return n


def build_rows(tafsir_rows, lemma_id_of, counter):
    lemmer = qalsadi.lemmatizer.Lemmatizer()
    words, lemma_links, new_lemmas = [], [], []
    fallback_count = 0

    for r in tqdm(tafsir_rows, desc="lemmatizing", unit="block"):
        text_arabic = r["text_arabic"]
        if not text_arabic:
            continue
        tokens = tokenize(text_arabic)
        if not tokens:
            continue

        results = lemmer.lemmatize_text(" ".join(tokens), all=True)
        if len(results) != len(tokens):
            fallback_count += 1
            results = [lemmer.lemmatize(tok, all=True) for tok in tokens]

        for position, (surface_form, candidates) in enumerate(zip(tokens, results), start=1):
            word_occurrence_id = f"{r['tafsir_id']}:{position}"
            words.append({
                "word_occurrence_id": word_occurrence_id,
                "surface_form": surface_form,
                "position_in_tafsir": position,
                "tafsir_id": r["tafsir_id"],
            })
            if not candidates:
                continue
            lemma_text = candidates[0]
            if lemma_text not in lemma_id_of:
                lemma_id_of[lemma_text] = f"L{counter}"
                counter += 1
                new_lemmas.append({"lemma_id": lemma_id_of[lemma_text], "text": lemma_text})
            lemma_links.append({
                "word_occurrence_id": word_occurrence_id,
                "lemma_id": lemma_id_of[lemma_text],
            })

    return words, new_lemmas, lemma_links, fallback_count


def main(book_id):
    tafsir_rows, _ = build_tafsir_rows(book_id)

    lemma_id_of = existing_lemmas()
    known = len(lemma_id_of)
    counter = next_index(lemma_id_of.values())

    words, new_lemmas, lemma_links, fallback_count = build_rows(
        tafsir_rows, lemma_id_of, counter
    )

    with graph_connection() as conn:
        run_batch(conn, CREATE_WORD, words)
        run_batch(conn, CREATE_LEMMA, new_lemmas)
        run_batch(conn, LINK_LEMMA, lemma_links)

    print(f"TafsirWordOccurrence: {len(words)} nodes + PART_OF_TAFSIR")
    print(f"TafsirLemma: {len(new_lemmas)} new (reused {known}), "
          f"HAS_TAFSIR_LEMMA: {len(lemma_links)} edges")
    print(f"blocks using per-word fallback: {fallback_count}/{len(tafsir_rows)}")