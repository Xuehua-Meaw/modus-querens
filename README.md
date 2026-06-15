# Modus Querens

**Reason over your notes — not vector similarity.**

A skill for Cursor, Claude Code, and OpenAI Codex. Query your notes and docs by reasoning over structure.

## Install

```bash
npx modus-querens install
npx modus-querens install -g
npx modus-querens install cursor claude-code
npx modus-querens install -g codex
```

| Scope | Flag | Paths |
|-------|------|-------|
| This repo | *(default)* | `.cursor/skills/`, `.claude/skills/`, `.agents/skills/` |
| All your projects | `-g` | `~/.cursor/skills/`, `~/.claude/skills/`, `~/.agents/skills/` |

Run without agent names to pick from an interactive list (↑↓ move, Space toggle, Enter confirm). `install -g` with no names updates agents already installed globally; if none exist yet, you pick which to add.

Restart your agent after installing.

## Uninstall

```bash
npx modus-querens uninstall
npx modus-querens uninstall -g
npx modus-querens uninstall cursor
```

Uninstall with no agent names removes the skill from **all** agents in that scope. Legacy paths from older installs (e.g. `~/.codex/skills/`) are cleaned up too.

Does **not** delete `.modus-querens/` indexes or run logs next to your notes.

## Usage

1. Point the agent at a folder of notes or docs.
2. Ask something like *"Ask my notes how X connects to Y"* or *"Query my knowledge base about …"*.
3. Optional index: `python skills/modus-querens/scripts/build_tree.py <corpus> --out .modus-querens/index`

Runs and indexes are written under `.modus-querens/` next to your corpus.

## License

MIT — see [LICENSE](LICENSE).
