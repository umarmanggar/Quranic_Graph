"""
Inti penggabungan: Root (2 sumber: quran_kg, hadith_kg) lalu Lemma (3 sumber:
quran_kg.Lemma, quran_kg.TafsirLemma, hadith_kg.Lemma), dedup pakai
ids.dedup_key() (lihat ids.py utk alasan normalisasi). Root duluan karena
Lemma->Root butuh root_id baru sudah ada.

Precedence saat key sama: quran menang (teks paling lengkap harakatnya),
lalu tafsir, baru hadith -- ejaan/teks yang tersimpan ikut sumber yang PERTAMA
bikin key itu; sumber berikutnya cuma menambah properti opsional (pos/
frequency/source dari hadith) kalau belum ada.

HAS_ROOT: hadith_kg sudah punya (Lemma)-[:HAS_ROOT]->(Root) langsung dipakai;
quran_kg cuma punya (WordOccurrence)-[:HAS_ROOT]->(Root) langsung (lewati
Lemma) jadi harus diinfer per-lemma dari kata2 yang memakainya (mayoritas
root kalau ada perselisihan -- jarang terjadi, dicatat kalau ada).
"""
import sys
from pathlib import Path
from collections import defaultdict, Counter

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import graph_connection, run_batch, cypher_rows
from ids import dedup_key, strip_homonym_suffix

CREATE_ROOT = """
UNWIND $rows AS row
CREATE (:Root {root_id: row.root_id, arabic_trilateral: row.arabic_trilateral, english_trilateral: row.english_trilateral})
"""

CREATE_LEMMA = """
UNWIND $rows AS row
CREATE (:Lemma {lemma_id: row.lemma_id, text: row.text, pos: row.pos, frequency: row.frequency, source: row.source})
"""

LINK_HAS_ROOT = """
UNWIND $rows AS row
MATCH (l:Lemma {lemma_id: row.lemma_id})
MATCH (r:Root {root_id: row.root_id})
CREATE (l)-[:HAS_ROOT]->(r)
"""


def merge_roots(conn):
    root_key_to_id = {}
    root_id_to_node = {}
    quran_root_id_to_new = {}
    hadith_root_text_to_new = {}
    counter = 0

    for r in cypher_rows(conn, "quran_kg", "MATCH (r:Root) RETURN r.root_id, r.arabic_trilateral, r.english_trilateral",
                          ["root_id", "arabic_trilateral", "english_trilateral"], desc="Root (quran)"):
        key = dedup_key(r["arabic_trilateral"])
        if key not in root_key_to_id:
            root_key_to_id[key] = counter
            root_id_to_node[counter] = {
                "root_id": counter,
                "arabic_trilateral": r["arabic_trilateral"],
                "english_trilateral": r["english_trilateral"],
            }
            counter += 1
        quran_root_id_to_new[r["root_id"]] = root_key_to_id[key]

    for r in cypher_rows(conn, "hadith_kg", "MATCH (r:Root) RETURN r.root", ["root"], desc="Root (hadith)"):
        key = dedup_key(r["root"])
        if key not in root_key_to_id:
            root_key_to_id[key] = counter
            root_id_to_node[counter] = {
                "root_id": counter,
                "arabic_trilateral": r["root"],
                "english_trilateral": None,
            }
            counter += 1
        hadith_root_text_to_new[r["root"]] = root_key_to_id[key]

    return root_id_to_node, quran_root_id_to_new, hadith_root_text_to_new


def merge_lemmas(conn):
    lemma_key_to_id = {}
    lemma_id_to_node = {}
    quran_lemma_id_to_new = {}
    tafsir_lemma_id_to_new = {}
    hadith_lemma_id_to_new = {}
    counter = 0
    stats = {"quran_new": 0, "tafsir_new": 0, "tafsir_reused": 0, "hadith_new": 0, "hadith_reused": 0, "hadith_enriched": 0}

    for r in cypher_rows(conn, "quran_kg", "MATCH (l:Lemma) RETURN l.lemma_id, l.text", ["lemma_id", "text"], desc="Lemma (quran)"):
        key = dedup_key(r["text"])
        if key not in lemma_key_to_id:
            lemma_key_to_id[key] = counter
            lemma_id_to_node[counter] = {"lemma_id": counter, "text": r["text"], "pos": None, "frequency": None, "source": None}
            counter += 1
            stats["quran_new"] += 1
        quran_lemma_id_to_new[r["lemma_id"]] = lemma_key_to_id[key]

    for r in cypher_rows(conn, "quran_kg", "MATCH (l:TafsirLemma) RETURN l.lemma_id, l.text", ["lemma_id", "text"], desc="TafsirLemma"):
        key = dedup_key(r["text"])
        if key not in lemma_key_to_id:
            lemma_key_to_id[key] = counter
            lemma_id_to_node[counter] = {"lemma_id": counter, "text": r["text"], "pos": None, "frequency": None, "source": None}
            counter += 1
            stats["tafsir_new"] += 1
        else:
            stats["tafsir_reused"] += 1
        tafsir_lemma_id_to_new[r["lemma_id"]] = lemma_key_to_id[key]

    for r in cypher_rows(conn, "hadith_kg", "MATCH (l:Lemma) RETURN l.lemma_id, l.lemma, l.pos, l.frequency",
                          ["lemma_id", "lemma", "pos", "frequency"], desc="Lemma (hadith)"):
        key = dedup_key(r["lemma"])
        if key not in lemma_key_to_id:
            lemma_key_to_id[key] = counter
            lemma_id_to_node[counter] = {
                "lemma_id": counter, "text": strip_homonym_suffix(r["lemma"]),
                "pos": r["pos"], "frequency": r["frequency"], "source": "qabas",
            }
            counter += 1
            stats["hadith_new"] += 1
        else:
            stats["hadith_reused"] += 1
            node = lemma_id_to_node[lemma_key_to_id[key]]
            if node["source"] is None:
                node["pos"], node["frequency"], node["source"] = r["pos"], r["frequency"], "qabas"
                stats["hadith_enriched"] += 1
        hadith_lemma_id_to_new[r["lemma_id"]] = lemma_key_to_id[key]

    return lemma_id_to_node, quran_lemma_id_to_new, tafsir_lemma_id_to_new, hadith_lemma_id_to_new, stats


def hadith_has_root_edges(conn, hadith_lemma_id_to_new, hadith_root_text_to_new):
    edges = set()
    for r in cypher_rows(conn, "hadith_kg", "MATCH (l:Lemma)-[:HAS_ROOT]->(r:Root) RETURN l.lemma_id, r.root",
                          ["lemma_id", "root"], desc="Lemma-HAS_ROOT (hadith)"):
        new_lemma_id = hadith_lemma_id_to_new.get(r["lemma_id"])
        new_root_id = hadith_root_text_to_new.get(r["root"])
        if new_lemma_id is not None and new_root_id is not None:
            edges.add((new_lemma_id, new_root_id))
    return edges


def quran_inferred_has_root_edges(conn, quran_lemma_id_to_new, quran_root_id_to_new):
    word_lemma = cypher_rows(conn, "quran_kg", "MATCH (w:WordOccurrence)-[:HAS_LEMMA]->(l:Lemma) RETURN w.location, l.lemma_id",
                              ["location", "lemma_id"], desc="WordOccurrence-HAS_LEMMA (quran)")
    word_root = cypher_rows(conn, "quran_kg", "MATCH (w:WordOccurrence)-[:HAS_ROOT]->(r:Root) RETURN w.location, r.root_id",
                             ["location", "root_id"], desc="WordOccurrence-HAS_ROOT (quran)")

    loc_to_lemma = {r["location"]: r["lemma_id"] for r in word_lemma}
    loc_to_root = {r["location"]: r["root_id"] for r in word_root}

    lemma_to_roots = defaultdict(Counter)
    for loc, old_lemma_id in loc_to_lemma.items():
        old_root_id = loc_to_root.get(loc)
        if old_root_id is not None:
            lemma_to_roots[old_lemma_id][old_root_id] += 1

    edges = set()
    disagreements = []
    for old_lemma_id, root_counts in lemma_to_roots.items():
        new_lemma_id = quran_lemma_id_to_new[old_lemma_id]
        if len(root_counts) > 1:
            disagreements.append((old_lemma_id, dict(root_counts)))
        best_root_id, _ = root_counts.most_common(1)[0]
        edges.add((new_lemma_id, quran_root_id_to_new[best_root_id]))

    return edges, disagreements


def main():
    with graph_connection() as conn:
        print("  merging Root (quran_kg + hadith_kg)...", flush=True)
        root_id_to_node, quran_root_id_to_new, hadith_root_text_to_new = merge_roots(conn)
        print(f"    -> {len(root_id_to_node):,} Root unik", flush=True)

        print("  merging Lemma (quran_kg + TafsirLemma + hadith_kg)...", flush=True)
        (lemma_id_to_node, quran_lemma_id_to_new, tafsir_lemma_id_to_new,
         hadith_lemma_id_to_new, stats) = merge_lemmas(conn)
        print(f"    -> {len(lemma_id_to_node):,} Lemma unik", flush=True)

        print("  membangun HAS_ROOT (hadith langsung + quran inferred)...", flush=True)
        hadith_edges = hadith_has_root_edges(conn, hadith_lemma_id_to_new, hadith_root_text_to_new)
        quran_edges, disagreements = quran_inferred_has_root_edges(conn, quran_lemma_id_to_new, quran_root_id_to_new)
        has_root_edges = hadith_edges | quran_edges

        print("  menulis Root...", flush=True)
        run_batch(conn, CREATE_ROOT, list(root_id_to_node.values()))
        print("  menulis Lemma...", flush=True)
        run_batch(conn, CREATE_LEMMA, list(lemma_id_to_node.values()))
        print("  menulis HAS_ROOT...", flush=True)
        run_batch(conn, LINK_HAS_ROOT, [{"lemma_id": l, "root_id": r} for l, r in has_root_edges])

    print(f"Root: {len(root_id_to_node)} nodes (naive sum quran+hadith would be larger; dedup merged the overlap)")
    print(f"Lemma: {len(lemma_id_to_node)} nodes -- quran_new={stats['quran_new']} "
          f"tafsir_new={stats['tafsir_new']} tafsir_reused={stats['tafsir_reused']} "
          f"hadith_new={stats['hadith_new']} hadith_reused={stats['hadith_reused']} "
          f"hadith_enriched_existing={stats['hadith_enriched']}")
    print(f"HAS_ROOT: {len(has_root_edges)} edges (hadith-direct={len(hadith_edges)}, quran-inferred={len(quran_edges)})")
    if disagreements:
        print(f"  WARNING: {len(disagreements)} quran lemma(s) had disagreeing roots across their occurrences "
              f"(majority root used): sample={disagreements[:5]}")


if __name__ == "__main__":
    main()
