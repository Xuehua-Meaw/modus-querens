#!/usr/bin/env python3
"""Deterministic table-of-contents tree builder for Modus Querens.

Stdlib only. No LLM, no embeddings, no third-party deps. Turns a corpus of
Markdown/text files into per-doc `structure.json` section trees plus a
`_catalog.json`, so a coding agent can navigate by reasoning and read tight
source ranges on demand.

Usage:
    python build_tree.py <corpus_dir> [--out .modus-querens/index]
                                      [--ext .md,.markdown,.txt]

Markdown headings (# .. ######) define the hierarchy; fenced code blocks are
ignored. Files without headings become a single whole-file node. PDFs are not
parsed here — convert them to Markdown first (PDF parsing flattens structure).
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from corpus_utils import iter_corpus_files, read_corpus_lines, resolve_corpus, safe_rel_path

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


def slugify(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower())
    return re.sub(r"-{2,}", "-", text).strip("-") or "doc"


def extract_headings(lines: list[str]) -> list[dict]:
    """Return [{level, title, line}] for real headings, skipping code fences."""
    headings: list[dict] = []
    in_fence = False
    for i, raw in enumerate(lines, start=1):
        if FENCE_RE.match(raw):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = HEADING_RE.match(raw)
        if m:
            headings.append({"level": len(m.group(1)), "title": m.group(2).strip(), "line": i})
    return headings


def build_structure(lines: list[str], doc_stem: str) -> list[dict]:
    total = len(lines)
    headings = extract_headings(lines)
    if not headings:
        return [{"title": doc_stem, "line_start": 1, "line_end": total, "summary": "", "nodes": []}]

    # A section spans until the next heading at the same or shallower level (its
    # children are nested sub-ranges inside that span).
    flat: list[dict] = []
    for idx, h in enumerate(headings):
        end = total
        for nxt in headings[idx + 1:]:
            if nxt["level"] <= h["level"]:
                end = nxt["line"] - 1
                break
        flat.append({
            "level": h["level"],
            "title": h["title"],
            "line_start": h["line"],
            "line_end": end,
            "summary": "",
            "nodes": [],
        })

    roots: list[dict] = []
    stack: list[dict] = []
    # Optional preface: non-blank content before the first heading.
    if headings[0]["line"] > 1 and any(l.strip() for l in lines[: headings[0]["line"] - 1]):
        roots.append({
            "title": "(preface)", "line_start": 1, "line_end": headings[0]["line"] - 1,
            "summary": "", "nodes": [],
        })

    for node in flat:
        level = node.pop("level")
        node["_level"] = level
        while stack and stack[-1]["_level"] >= level:
            stack.pop()
        (stack[-1]["nodes"] if stack else roots).append(node)
        stack.append(node)

    _strip_levels(roots)
    return roots


def _strip_levels(nodes: list[dict]) -> None:
    for n in nodes:
        n.pop("_level", None)
        _strip_levels(n.get("nodes", []))


def assign_node_ids(nodes: list[dict], counter: list[int]) -> None:
    for n in nodes:
        counter[0] += 1
        n_ordered = {"node_id": f"{counter[0]:04d}"}
        n_ordered.update(n)
        n.clear()
        n.update(n_ordered)
        assign_node_ids(n.get("nodes", []), counter)


def first_h1(lines: list[str]) -> str:
    for h in extract_headings(lines):
        if h["level"] == 1:
            return h["title"]
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description="Build Modus Querens section trees.")
    ap.add_argument("corpus_dir")
    ap.add_argument("--out", default=".modus-querens/index")
    ap.add_argument("--ext", default=".md,.markdown,.txt")
    args = ap.parse_args()

    corpus = resolve_corpus(args.corpus_dir)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    exts = {e if e.startswith(".") else f".{e}" for e in args.ext.split(",")}

    catalog: list[dict] = []
    files = iter_corpus_files(corpus, exts)
    for path in files:
        try:
            lines = read_corpus_lines(path)
        except (OSError, UnicodeDecodeError):
            continue
        rel = Path(safe_rel_path(path, corpus))
        slug = slugify(str(rel.with_suffix("")))
        doc_type = "markdown" if path.suffix.lower() in {".md", ".markdown"} else "text"
        structure = build_structure(lines, path.stem)
        assign_node_ids(structure, [0])
        tree = {
            "doc_slug": slug,
            "doc_path": str(rel).replace("\\", "/"),
            "doc_type": doc_type,
            "doc_description": first_h1(lines),
            "mtime": int(path.stat().st_mtime),
            "structure": structure,
        }
        (out / f"{slug}.json").write_text(
            json.dumps(tree, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        catalog.append({
            "doc_slug": slug,
            "doc_path": tree["doc_path"],
            "doc_type": doc_type,
            "doc_description": tree["doc_description"],
            "mtime": tree["mtime"],
        })

    (out / "_catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Indexed {len(catalog)} document(s) -> {out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
