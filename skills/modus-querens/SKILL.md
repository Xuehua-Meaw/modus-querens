---
name: modus-querens
description: >-
  Modus Querens — query a personal knowledge base (notes, papers, a folder of
  docs) by reasoning over structure instead of vector similarity. Builds/uses a
  file-based table-of-contents tree, dispatches investigation sub-agents that
  report back and leave an audit trail, then synthesizes a layered, source-cited
  answer. Use when the user wants to ask questions, find hidden links, or
  synthesize answers across their own corpus/notes/documents, says "ask my
  notes/knowledge base", or mentions vectorless / reasoning-based / file-based
  retrieval over a personal corpus.
license: MIT
compatibility: Cursor, Claude Code, OpenAI Codex; Python 3.10+ optional for scripts (build_tree.py stdlib; build_bm25.py needs rank-bm25)
metadata:
  author: Xuehua-Meaw
  version: "0.1.34"
---

# Modus Querens

> *modus ponens*: from `X` and `X → Y`, conclude `Y`.
> **modus querens** *(coined)*: from a *corpus* and a *question*, **reason** your
> way to a grounded conclusion — and show which sources made it true.

Modus Querens answers questions over a personal knowledge base by **reasoning over
structure**, not vector similarity. It runs inside your coding agent's harness —
no vector DB, no server, no embedding pipeline.

**Core stance:** *similarity ≠ relevance*. Cite sources. Surface gaps instead of
bluffing. Keep it **cheap**: cite lightly; spell out *why* only for load-bearing
or contested claims.

## When to use

- The user asks a question to be answered **from their own files** (notes,
  papers, reports, a docs/ folder, a wiki, an exported corpus).
- They want synthesis, hidden links, or multi-hop answers across many documents.
- They mention "ask my notes", "query my knowledge base", "vectorless RAG",
  or reasoning-based retrieval over a corpus.

## When NOT to use

- General coding tasks in the active repo (use normal tools).
- A question answerable from a single open file (just read it).
- Production-scale RAG for an app (use a dedicated stack instead).

## Map (file-based)

**File-based tree navigation** — see [strategy-filebased.md](strategy-filebased.md).
Build or refresh `.modus-querens/index/`, reason over section trees, read source
ranges on demand.

Optional **BM25 lexical recall** (`build_bm25.py` + `search_bm25.py`, needs
`rank-bm25`) covers multilingual notes (CJK, kana, Hangul, Thai, Cyrillic,
Arabic, Devanagari, Greek, Hebrew, Latin). Native codebase search (e.g.
**Cursor**) also belongs in **Map**. Treat hits as **candidates** only;
confirm by reading the section.

## The loop

```
Frame  ->  Map  ->  Investigate  ->  Synthesize  ->  Audit (light)
```

1. **Frame.** 2–5 probes + a sufficiency note → `plan.md`.
2. **Map.** File-based index (+ optional native search). See [strategy-filebased.md](strategy-filebased.md).
3. **Investigate.** One sub-agent per probe (parallel). Each reads sources, returns
   findings, and **must write** `<run>/investigations/<probe-slug>.md` to disk.
   **Before Synthesize:** confirm every probe file exists; if missing, re-dispatch
   or write from the sub-agent return yourself.
4. **Synthesize.** Merge investigation notes from disk into a layered, cited answer.
5. **Audit.** Persist plan + investigation notes (+ optional `answer.md`).

## Sub-agents

- Dispatch sub-agents in parallel, one per probe.
- Give each: the probe, corpus root, index path, run folder, and **exact audit path**.
- Each **returns** a tight summary and **writes** its audit note — both are required.
- You synthesize from the on-disk notes — do not re-read everything they read.

### Cursor (Task tool) — required settings

Investigation sub-agents **must be able to write files**. Read-only sub-agents
cannot complete Investigate; they will return markdown in chat but skip the audit
trail.

| Setting | Investigate phase | Why |
| --- | --- | --- |
| `readonly` | **`false`** (omit or explicit) | Must write `<run>/investigations/*.md` |
| `subagent_type` | `generalPurpose` or `explore` | `explore` only if it can write in your harness |
| `run_in_background` | parallel OK | One Task per probe |

**Do not** set `readonly: true` for Investigate sub-agents. Reserve read-only
agents for Map-only reconnaissance if needed — never for probe investigations.

**Parent agent checklist** after Investigate returns:

1. `Glob` or list `<run>/investigations/` — expect one file per probe.
2. If any probe file is missing, **do not proceed to Synthesize** until fixed.
3. Fix path: re-dispatch with `readonly: false` and the write path in the prompt,
   or paste the sub-agent return into the missing file yourself, then continue.

**Investigation prompt must include** (copy/adapt):

```
Write your audit note to this exact path (required, not optional):
<run>/investigations/<probe-slug>.md

Format: Summary, Evidence (cited bullets), Gaps.
Do not finish until the file exists on disk.
```

Other hosts (Claude Code, Codex): same rule — sub-agents need write access to the
run folder during Investigate.

## Output contract

- **Headline answer** first in natural reading order.
- **Branches** only when multi-faceted.
- **Inline citations** — `(<path> §<heading>)`, `(<file> p.<page>)`, or `(<file>:<line>)`.
- **Open questions / gaps** when something material is missing.

## Lightness rules

- Cite the source by default, not a paragraph of justification.
- Spell out `evidence ⇒ claim (because … under …)` only for load-bearing or contested claims.
- Never strip a condition to make a claim look cleaner.
- Gather multiple spans for comparative/multi-hop questions.
- Prefer whole sections over fragments.

## Audit folder

```
.modus-querens/
├── index/
│   ├── _catalog.json
│   ├── _bm25_meta.json      # optional BM25 manifest
│   ├── _bm25.pkl            # optional BM25 index
│   └── <doc-slug>.json
└── runs/
    └── <YYYYMMDD-HHMM>-<slug>/
        ├── plan.md
        ├── investigations/
        │   └── <probe-slug>.md
        └── answer.md
```

Add `.modus-querens/` to `.gitignore` if you do not want runs tracked.

## Details

- Full method and evidence discipline: [reference.md](reference.md).
- File-based strategy: [strategy-filebased.md](strategy-filebased.md).
- Index builders: `scripts/build_tree.py` (stdlib; Markdown headings → trees),
  `scripts/build_bm25.py` (optional `rank-bm25`; section-level lexical recall).
