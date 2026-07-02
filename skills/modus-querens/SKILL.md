---
name: modus-querens
description: Query a personal knowledge base (notes, papers, docs) by reasoning over structure instead of vector similarity. Use when the user wants to ask questions across their own corpus/notes/documents, says "ask my notes/knowledge base", or mentions vectorless/reasoning-based/file-based retrieval.
version: "0.1.36"
---

# Modus Querens

**Reason over your notes, not vector similarity.**

Query a personal knowledge base (notes, papers, docs, wiki) by reasoning over structure. No vector DB, no embeddings, no server — just file-based tree navigation and parallel investigation sub-agents.

## Trigger patterns

Use this skill when the user:
- Says **"ask my notes"** or **"query my knowledge base"**
- Points to a folder of notes/docs and asks a synthesis question
- Wants to find hidden links across multiple documents
- Mentions "vectorless RAG" or "reasoning-based retrieval"
- Asks a multi-hop question that requires reading across several files

**Do NOT use** for:
- Single-file questions (just Read it)
- General coding tasks in the active repo
- Production-scale RAG systems (use dedicated stacks)

## Quick start

1. **Check for index**: Look for `.modus-querens/index/_catalog.json`
2. **No index?** Ask user for corpus path, then:
   ```bash
   python skills/modus-querens/scripts/build_tree.py <corpus> --out .modus-querens/index
   ```
3. **Run the loop**: Frame → Map → Investigate → Synthesize → Audit

## Core principles

- **Structure > similarity**: Navigate section trees, don't embed-and-search
- **Cite everything**: `(notes/foo.md §Heading)` format
- **Surface gaps**: Report what's missing instead of guessing
- **Whole sections**: Read complete sections, not fragments
- **Parallel probes**: One sub-agent per question, all write audit trails

## Index structure

`.modus-querens/index/` contains:
- `_catalog.json` — list of all docs with one-line descriptions
- `<doc-slug>.json` — section tree for each document (node_id, title, line ranges, optional summaries)
- `_bm25_meta.json` + `_bm25.pkl` — optional BM25 lexical index (multilingual: CJK, kana, Hangul, Thai, Cyrillic, Arabic, etc.)

Build with:
```bash
python skills/modus-querens/scripts/build_tree.py <corpus> --out .modus-querens/index
python skills/modus-querens/scripts/build_bm25.py <corpus> --index .modus-querens/index  # optional
```

See [strategy-filebased.md](strategy-filebased.md) for schema details.

## The loop

```
Frame → Map → Investigate → Synthesize → Audit
```

### 1. Frame (2-5 probes)
Break the user's question into 2-5 focused probes. Write `<run>/plan.md`:
```markdown
# Plan

## Question
<user's original question>

## Probes
1. <specific sub-question>
2. <specific sub-question>
...

## Sufficiency
These probes are sufficient because <reasoning>.
```

### 2. Map (find relevant sections)
- Read `.modus-querens/index/_catalog.json` → pick relevant docs
- Read `<doc-slug>.json` trees → identify sections by reasoning
- **Optional BM25 recall**: `python scripts/search_bm25.py "<probe>" --index .modus-querens/index`
  - Requires: `pip install rank-bm25` and pre-built index
  - Treat hits as **candidates only** — always read the section to confirm

### 3. Investigate (parallel sub-agents)
Spawn one sub-agent per probe. Each:
- Reads catalog + trees + source sections
- Writes `<run>/investigations/<probe-slug>.md`
- Returns tight summary

**Critical**: Verify all investigation files exist before proceeding.

### 4. Synthesize
Read investigation notes from disk (don't re-read sources). Produce:
- **Headline answer** (natural reading order)
- **Inline citations**: `(path/to/file.md §Section Title)`
- **Gaps**: Report missing info instead of guessing

### 5. Audit
All artifacts already written:
- `plan.md` (from Frame)
- `investigations/*.md` (from Investigate)
- Optional: Write `answer.md` with the final synthesis

## Sub-agents

Dispatch sub-agents in parallel, one per probe. Each sub-agent:
- Receives: probe question, corpus root, index path, run folder, **exact output file path**
- Returns: tight summary (for chat)
- Writes: full audit note to `<run>/investigations/<probe-slug>.md`

### Claude Code (Agent tool)

```python
# Example: spawn investigate sub-agents in parallel
from pathlib import Path

run_dir = Path(".modus-querens/runs/20260702-1430-residuals")
probes = [
    "How do residual streams enable gradient flow?",
    "What role do layer norms play in residual connections?",
]

# Dispatch all probes in parallel
for i, probe in enumerate(probes):
    slug = probe.lower().replace(" ", "-")[:40]
    output_path = run_dir / "investigations" / f"{slug}.md"
    
    Agent(
        description=f"Investigate probe {i+1}",
        prompt=f"""
Investigate: {probe}

Corpus: ./notes/
Index: .modus-querens/index/
Output: {output_path}

Steps:
1. Read _catalog.json and pick relevant docs
2. Read structure trees and locate sections
3. Fetch source text (whole sections, not fragments)
4. Write audit note to {output_path}

Format:
## Summary
<1-2 sentence answer>

## Evidence
- <citation> §<section>: <key point>

## Gaps
<what's missing, if anything>
""",
        mode="auto"  # or omit for default
    )
```

After all sub-agents return, **verify all files exist** before Synthesize:
```python
expected = [run_dir / "investigations" / f"{slug}.md" for slug in probe_slugs]
missing = [p for p in expected if not p.exists()]
if missing:
    # Re-dispatch or write from sub-agent return
```

### Cursor (Task tool)

Use `Task(readonly=false, ...)` and include the output path in the prompt. Same verification: check all investigation files exist before Synthesize.

## Citation rules

- **Format**: `(path/to/file.md §Section Title)` or `(file.pdf p.42)` or `(file:123)`
- **Default**: Always cite; skip lengthy justification
- **Load-bearing claims**: Spell out `evidence ⇒ claim (because X under Y)` only when contested or critical
- **Never strip conditions** to make claims look cleaner
- **Prefer whole sections** over fragments
- **Report gaps** instead of guessing

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
