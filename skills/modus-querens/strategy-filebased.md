# Strategy: File-based

Default for all hosts. No vector DB, no embeddings. Build a table-of-contents
**tree** for each document as plain files, navigate by reasoning, and read source
slices on demand.

## 1. Build / refresh the index

The index lives in `.modus-querens/index/`. Each document gets a section tree;
`_catalog.json` lists every document with a one-line description.

**Prefer Markdown/text.** Real `#` heading hierarchy is reliable. PDF parsing
often flattens structure — convert to Markdown first when you can.

Two ways to build it:

- **Deterministic:** run the helper for Markdown/text:
  ```bash
  python scripts/build_tree.py <corpus_dir> --out .modus-querens/index
  python scripts/build_bm25.py <corpus_dir> --index .modus-querens/index --rebuild-trees
  ```
  BM25 needs `pip install rank-bm25` (optional; tree-only works without it).
- **Agent-authored:** read each doc and write the tree yourself; fill `summary`
  only for load-bearing nodes.

Store each doc's `mtime` in the catalog and rebuild only changed files.

### Node schema

```jsonc
// .modus-querens/index/<doc-slug>.json
{
  "doc_slug": "attention-residuals",
  "doc_path": "notes/attention-residuals.md",
  "doc_type": "markdown",
  "doc_description": "One sentence that distinguishes this doc from the others.",
  "mtime": 1718000000,
  "structure": [
    {
      "node_id": "0001",
      "title": "Residual streams",
      "line_start": 12,
      "line_end": 48,
      "summary": "",
      "nodes": []
    }
  ]
}
```

Keep **only structure + summaries** in the tree. Read source files at query time.

## 2. Retrieve by tree search

```
A. DOC SELECT — read _catalog.json; pick relevant docs by description.

A'. BM25 RECALL (optional) — search_bm25.py or read _bm25_meta.json + top sections.
    Hits are candidates only; confirm by reading the section.

B. TREE SEARCH — read structure.json; reason which node_ids hold the answer.

C. FETCH — read only each node's source range (whole sections, not fragments).

D. ANSWER — synthesize from fetched text; cite (doc_path §title). Widen once,
   then report gaps rather than guessing.
```

## 3. Tools

| Step | Use |
| --- | --- |
| List docs | `Read .modus-querens/index/_catalog.json` |
| Read tree | `Read .modus-querens/index/<doc-slug>.json` |
| BM25 recall | `python scripts/search_bm25.py "<probe>" --index .modus-querens/index` |
| Read source | `Read(doc_path, offset, limit)` / `Grep` |

`Glob` discovers new files; `Grep` confirms a term appears where the tree implied.

## 4. Optional recall

**BM25 (lexical, not vector):** section-level index at `_bm25_meta.json` +
`_bm25.pkl`. Built by `build_bm25.py` with `rank-bm25`. Tokenizer `mq_v2`
covers CJK, Japanese kana, Korean, Thai, Cyrillic, Arabic, Devanagari, Greek,
Hebrew, and Latin (NFKC-normalized). Same discipline as tree search — candidates
only; always read the section range. Rebuild after upgrading tokenizer version.

**Host search (Cursor and similar):** codebase or semantic search during **Map**
when it helps. Hits are candidates, not answers — always read the section range.

## 5. With sub-agents

Give each investigation sub-agent the probe, corpus root, index path, run folder,
and the **exact output path** for its audit note. It runs steps B–C, returns a
tight summary, and **writes** `<run>/investigations/<probe-slug>.md`.

### Cursor enforcement

When using the **Task** tool for Investigate:

- Set **`readonly: false`** — never `readonly: true`.
- Put the full audit file path in the prompt; require the sub-agent to confirm
  the write before finishing.
- Parent agent: **verify** all `investigations/*.md` exist before Synthesize.
  If a sub-agent only returned chat text (Ask/read-only mode), the parent must
  write the file or re-dispatch with write access.

Read-only sub-agents are OK for **Map** scouting only, not for Investigate.

## Example

Question: *"How do my notes connect residual streams to gradient flow?"*

1. **Frame** → three probes + sufficiency note.
2. **Map** → `_catalog.json` → tree search → four sections.
3. **Investigate** → sub-agents read sections; one flags a condition on the link.
4. **Synthesize** → headline, branches, citations, open question for gaps.
5. **Audit** → `plan.md`, investigation notes, optional `answer.md`.
