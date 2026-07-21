"""
Tahap 2 - node Root & Lemma + edge HAS_ROOT.
Dedup sudah dilakukan di tahap 1 (python), jadi di sini murni CREATE dari daftar
unik. Meniru root_lemma.py Quran. Root diidentifikasi by string arab (bukan id,
ALMA tidak memberi root_id).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import graph_connection, run_batch, analyzed_rows, DEFAULT_GRAPH

ANALYZED = "hadith_analyzed.db"

CREATE_ROOT = """
UNWIND $rows AS row
CREATE (:Root {root: row.root})
"""

CREATE_LEMMA = """
UNWIND $rows AS row
CREATE (:Lemma {
  lemma_id: row.lemma_id,
  lemma: row.lemma,
  pos: row.pos,
  frequency: row.frequency,
  source: 'qabas'
})
"""

# HAS_ROOT: Lemma -> Root (lema yg punya root). root bisa null utk sebagian lema.
LINK_ROOT = """
UNWIND $rows AS row
MATCH (l:Lemma {lemma_id: row.lemma_id})
MATCH (r:Root {root: row.root})
CREATE (l)-[:HAS_ROOT]->(r)
"""


def main():
    roots = [{"root": r["root"]} for r in analyzed_rows(ANALYZED, "SELECT root FROM root")]
    lemmas = analyzed_rows(ANALYZED,
        "SELECT lemma_id, lemma, pos, root, frequency FROM lema")

    lemma_nodes = [{
        "lemma_id": r["lemma_id"], "lemma": r["lemma"],
        "pos": r["pos"], "frequency": r["frequency"],
    } for r in lemmas]

    root_links = [{"lemma_id": r["lemma_id"], "root": r["root"]}
                  for r in lemmas if r["root"]]

    with graph_connection(DEFAULT_GRAPH) as conn:
        run_batch(conn, CREATE_ROOT, roots)
        run_batch(conn, CREATE_LEMMA, lemma_nodes)
        run_batch(conn, LINK_ROOT, root_links)

    print(f"Root: {len(roots)} nodes, Lemma: {len(lemma_nodes)} nodes, HAS_ROOT: {len(root_links)} edges")


if __name__ == "__main__":
    main()
