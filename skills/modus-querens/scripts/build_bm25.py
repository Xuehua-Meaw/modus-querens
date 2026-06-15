#!/usr/bin/env python3
"""Build a section-level BM25 recall index for Modus Querens.

Requires: pip install rank-bm25  (or uv add rank-bm25)

Usage:
    python build_bm25.py <corpus_dir> [--index .modus-querens/index]
    python build_bm25.py <corpus_dir> --rebuild-trees   # refresh trees first

Reads per-doc tree JSON + source files; writes _bm25_meta.json and _bm25.pkl.
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from corpus_utils import (
    MAX_INDEXED_NODES,
    TOKENIZER_VERSION,
    flatten_tree_doc,
    iter_corpus_files,
    read_corpus_lines_bounded,
    resolve_corpus,
)

BM25_META = "_bm25_meta.json"
BM25_PKL = "_bm25.pkl"
SCHEMA_VERSION = 1


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _atomic_write_json(path: Path, data: dict) -> None:
    payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    _atomic_write_bytes(path, payload)


def _import_bm25():
    try:
        from rank_bm25 import BM25Okapi
    except ImportError as exc:
        raise SystemExit(
            "rank-bm25 is required: pip install rank-bm25\n"
            "Tree-only indexing works without it via build_tree.py."
        ) from exc
    try:
        from importlib.metadata import version as pkg_version
        ver = pkg_version("rank-bm25")
    except Exception:
        ver = "unknown"
    return BM25Okapi, ver


def _maybe_rebuild_trees(corpus: Path, index_dir: Path, exts: str) -> None:
    build_tree = Path(__file__).with_name("build_tree.py")
    if not build_tree.is_file():
        return
    subprocess.run(
        [sys.executable, str(build_tree), str(corpus), "--out", str(index_dir), "--ext", exts],
        check=True,
    )


def build_bm25_index(corpus: Path, index_dir: Path, exts: set[str]) -> dict:
    BM25Okapi, rank_bm25_version = _import_bm25()

    skipped: dict[str, int] = {
        "missing_tree": 0,
        "read_error": 0,
        "oversize_file": 0,
        "oversize_lines": 0,
        "decode_error": 0,
        "zero_tokens": 0,
        "invalid_range": 0,
    }

    tokenized_corpus: list[list[str]] = []
    meta_rows: list[dict] = []
    sources: dict[str, dict] = {}

    tree_files = sorted(p for p in index_dir.glob("*.json") if p.name not in {BM25_META, "_catalog.json"})
    for tree_path in tree_files:
        try:
            tree = json.loads(tree_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            skipped["missing_tree"] += 1
            continue

        doc_slug = tree.get("doc_slug", tree_path.stem)
        doc_path = tree.get("doc_path", "")
        source = corpus / doc_path.replace("/", os.sep)
        if not source.is_file():
            skipped["missing_tree"] += 1
            continue

        lines, err = read_corpus_lines_bounded(source)
        if lines is None:
            skipped["read_error"] += 1
            if err:
                key = err.split(":", 1)[0]
                if key in skipped:
                    skipped[key] += 1
            continue

        try:
            source_stat = source.stat()
            tree_stat = tree_path.stat()
        except OSError:
            skipped["read_error"] += 1
            continue

        sources[doc_slug] = {
            "doc_path": doc_path,
            "source_mtime": int(source_stat.st_mtime),
            "tree_mtime": int(tree_stat.st_mtime),
        }

        for row in flatten_tree_doc(tree, lines):
            if row["line_start"] > row["line_end"]:
                skipped["invalid_range"] += 1
                continue
            if len(meta_rows) >= MAX_INDEXED_NODES:
                break
            tokenized_corpus.append(row.pop("tokens"))
            row["i"] = len(meta_rows)
            meta_rows.append(row)

    built_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    meta: dict = {
        "version": SCHEMA_VERSION,
        "built_at": built_at,
        "tokenizer": TOKENIZER_VERSION,
        "rank_bm25": rank_bm25_version,
        "node_count": len(meta_rows),
        "skipped": skipped,
        "limits": {
            "max_tokens_per_node": 2048,
            "max_file_bytes": 32 * 1024 * 1024,
            "max_indexed_nodes": MAX_INDEXED_NODES,
        },
        "sources": sources,
        "meta": meta_rows,
    }

    index_dir.mkdir(parents=True, exist_ok=True)
    pkl_path = index_dir / BM25_PKL
    meta_path = index_dir / BM25_META

    if not tokenized_corpus or not any(tokenized_corpus):
        if pkl_path.exists():
            pkl_path.unlink()
        _atomic_write_json(meta_path, meta)
        return meta

    bm25 = BM25Okapi(tokenized_corpus)
    meta["stats"] = {
        "N": len(tokenized_corpus),
        "avgdl": float(bm25.avgdl),
    }

    _atomic_write_json(meta_path, meta)
    _atomic_write_bytes(pkl_path, pickle.dumps(bm25, protocol=pickle.HIGHEST_PROTOCOL))
    return meta


def main() -> int:
    ap = argparse.ArgumentParser(description="Build Modus Querens BM25 recall index.")
    ap.add_argument("corpus_dir")
    ap.add_argument("--index", default=".modus-querens/index")
    ap.add_argument("--ext", default=".md,.markdown,.txt")
    ap.add_argument(
        "--rebuild-trees",
        action="store_true",
        help="Run build_tree.py before indexing (recommended on first build).",
    )
    args = ap.parse_args()

    corpus = resolve_corpus(args.corpus_dir)
    index_dir = Path(args.index)
    exts = {e if e.startswith(".") else f".{e}" for e in args.ext.split(",")}

    if args.rebuild_trees or not (index_dir / "_catalog.json").exists():
        _maybe_rebuild_trees(corpus, index_dir, args.ext)

    # Sanity: corpus has files
    files = iter_corpus_files(corpus, exts)
    if not files:
        print(f"No files with extensions {sorted(exts)} under {corpus}", file=sys.stderr)
        return 1

    meta = build_bm25_index(corpus, index_dir, exts)
    n = meta["node_count"]
    print(f"BM25 index: {n} node(s) -> {index_dir}/{BM25_META}")
    if n == 0:
        print("Warning: no indexable nodes (empty corpus or all skipped).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
