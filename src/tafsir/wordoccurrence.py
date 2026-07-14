import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import re

import qalsadi.lemmatizer
from tqdm import tqdm

from db import graph_connection, run_batch
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
CREATE (w)-[:HAS_LEMMA]->(l)
"""


def tokenize(text):
    tokens = []
    for raw in text.split():
        t = TOKEN_TRIM.sub("", raw)
        if t:
            tokens.append(t)
    return tokens


def main():
    tafsir_rows, _ = build_tafsir_rows()
    lemmer = qalsadi.lemmatizer.Lemmatizer()

    words, lemma_links = [], []
    lemma_id_of = {}
    fallback_count = 0

    for r in tqdm(tafsir_rows, desc="lemmatizing", unit="block"):
        text_arabic = r["text_arabic"]
        if not text_arabic:
            continue
        tokens = tokenize(text_arabic)
        if not tokens:
            continue

        joined = " ".join(tokens)
        results = lemmer.lemmatize_text(joined, all=True)
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
            if candidates:
                lemma_text = candidates[0]
                if lemma_text not in lemma_id_of:
                    lemma_id_of[lemma_text] = f"L{len(lemma_id_of)}"
                lemma_links.append({
                    "word_occurrence_id": word_occurrence_id,
                    "lemma_id": lemma_id_of[lemma_text],
                })

    lemmas = [{"lemma_id": lemma_id, "text": text} for text, lemma_id in lemma_id_of.items()]

    with graph_connection() as conn:
        run_batch(conn, CREATE_WORD, words)
        run_batch(conn, CREATE_LEMMA, lemmas)
        run_batch(conn, LINK_LEMMA, lemma_links)

    print(f"TafsirWordOccurrence: {len(words)} nodes + PART_OF_TAFSIR")
    print(f"TafsirLemma: {len(lemmas)} nodes, HAS_LEMMA: {len(lemma_links)} edges")
    print(f"blocks using per-word lemmatize fallback: {fallback_count}/{len(tafsir_rows)}")


if __name__ == "__main__":
    main()
