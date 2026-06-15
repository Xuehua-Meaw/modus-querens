# Modus Querens — reference

Depth material. Read when you need the full method or evidence discipline.

## The formulation

Classical inference rules name a *shape* of valid move:

- **modus ponens** — `X`, `X → Y` ⊢ `Y`.
- **modus tollens** — `¬Y`, `X → Y` ⊢ `¬X`.
- **modus querens** *(coined)* — given a **corpus** and a **question**, reason
  through the corpus's structure to a **grounded conclusion**, and keep visible
  the sources (and conditions) that license it.

The unit of a Modus Querens answer is, when you unfold it, a modus ponens with
its warrant kept attached:

```
raw evidence (X)  ⇒  claim (Y)   because warrant,   under conditions (Z)
```

Keep this shape in mind for load-bearing claims, but only *write it out* for the
few claims the answer hinges on, or where sources conflict.

## Relevance over similarity

Vector top-k returns what is *similar*; you want what is *relevant*, which often
requires a reasoning hop the embedding never makes.

- Treat search hits and tree summaries as **candidates**, never as the answer.
- Confirm by reading the actual section and checking it bears on the question.
- Gather **several** spans for comparative/multi-hop questions; one hit cannot
  settle a comparison.

## Citation discipline

- Format: `(<path> §<heading>)`, `(<file> p.<page>)`, or `(<file>:<line>)`.
- One citation per claim *cluster*, not per sentence.
- Cite the **smallest** locating unit you actually read (section/page/line).
- Never cite a document you did not open at that location.

## The `because` discipline (use sparingly)

Write the explicit warrant + conditions for a claim only when:

1. the answer **depends** on that claim,
2. sources **disagree**, or
3. the claim carries a **condition** that changes its meaning.

If the source says `X holds under Z`, never compress it to `X holds`. Silently
dropping conditions is the most damaging failure this skill can make.

## Robustness lessons

- **Similarity ≠ relevance.** Reason over structure; do not trust top-k blindly.
- **Do not under-retrieve.** One hit cannot answer multi-hop or comparative questions.
- **Preserve provenance.** Keep originals and cite path + location.
- **Chunk boundaries lose context.** Read whole sections; preserve conditions on claims.
- **Prefer Markdown hierarchy; distrust PDF structure.** Convert to Markdown when possible.
- **Stale index = wrong answers.** Track `mtime`; rebuild only changed docs.
- **Split large nodes.** Descend into children instead of stopping at a vague parent.

## Anti-patterns

- Building a vector DB, embedding pipeline, or server for a personal corpus.
- Re-drafting the answer in many passes when one synthesis pass is enough.
- Emitting per-claim evidence-trail tables, completion markers, or trace JSON.
- Re-reading, as the main agent, everything the sub-agents already read.
- Answering a comparison from a single source.
- Pasting full document text into the tree index.
- Dropping a condition to make a claim look cleaner.

## Audit folder

```
.modus-querens/
├── index/
│   ├── _catalog.json
│   ├── _links.json       # optional cross-doc links
│   └── <doc-slug>.json
└── runs/
    └── <YYYYMMDD-HHMM>-<slug>/
        ├── plan.md
        ├── investigations/
        │   └── <probe-slug>.md
        └── answer.md
```

`plan.md` and each `investigations/*.md` are the audit trail. Keep them short.
