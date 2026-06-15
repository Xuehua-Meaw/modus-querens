#!/usr/bin/env python3
"""Query the Modus Querens BM25 index (Map-phase recall helper).

Usage:
    python search_bm25.py "residual streams gradient" [--index .modus-querens/index] [--top 30]
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path

from corpus_utils import tokenize

BM25_META = "_bm25_meta.json"
BM25_PKL = "_bm25.pkl"
MAX_JSON_BYTES = 200 * 1024 * 1024


def load_index(index_dir: Path):
    meta_path = index_dir / BM25_META
    pkl_path = index_dir / BM25_PKL
    if not meta_path.is_file():
        raise SystemExit(f"Missing {meta_path} — run build_bm25.py first.")
    if meta_path.stat().st_size > MAX_JSON_BYTES:
        raise SystemExit(f"Index metadata too large: {meta_path}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("node_count", 0) == 0 or not pkl_path.is_file():
        return meta, None
    if pkl_path.stat().st_size > MAX_JSON_BYTES * 5:
        raise SystemExit(f"Index pickle too large: {pkl_path}")
    with pkl_path.open("rb") as fh:
        bm25 = pickle.load(fh)
    return meta, bm25


def search(index_dir: Path, query: str, top_k: int = 30) -> list[dict]:
    meta, bm25 = load_index(index_dir)
    qtok = tokenize(query, query=True)
    if not qtok:
        return []
    if bm25 is None:
        return []

    scores = bm25.get_scores(qtok)
    if not len(scores):
        return []
    if float(max(scores)) == 0.0:
        return []

    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

    hits: list[dict] = []
    for i in ranked[:top_k]:
        score = float(scores[i])
        row = dict(meta["meta"][i])
        row["score"] = score
        hits.append(row)
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description="Search Modus Querens BM25 index.")
    ap.add_argument("query")
    ap.add_argument("--index", default=".modus-querens/index")
    ap.add_argument("--top", type=int, default=30)
    args = ap.parse_args()

    hits = search(Path(args.index), args.query, top_k=args.top)
    if not hits:
        print("No BM25 hits (empty query, empty index, or no matching terms).", file=sys.stderr)
        return 1

    for h in hits:
        line = (
            f"{h['score']:.4f}\t{h['doc_path']}\t§{h['title']}\t"
            f"L{h['line_start']}-{h['line_end']}\tnode={h['node_id']}"
        )
        sys.stdout.buffer.write(line.encode("utf-8", errors="replace") + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
