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
  ```
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
| Read source | `Read(doc_path, offset, limit)` / `Grep` |

`Glob` discovers new files; `Grep` confirms a term appears where the tree implied.

## 4. Optional recall (Cursor and similar hosts)

When the harness offers codebase or semantic search, use it only during **Map** to
spot candidates before or alongside tree search. Hits are candidates, not
answers — always read the section range.

## 5. With sub-agents

Give each investigation sub-agent the probe, corpus root, index path, and run
folder. It runs steps B–C, returns a tight summary, and writes
`<run>/investigations/<probe-slug>.md`.

## Example

Question: *"How do my notes connect residual streams to gradient flow?"*

1. **Frame** → three probes + sufficiency note.
2. **Map** → `_catalog.json` → tree search → four sections.
3. **Investigate** → sub-agents read sections; one flags a condition on the link.
4. **Synthesize** → headline, branches, citations, open question for gaps.
5. **Audit** → `plan.md`, investigation notes, optional `answer.md`.
