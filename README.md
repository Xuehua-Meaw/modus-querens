# Modus Querens

**Reason over your notes — not vector similarity.**

A skill for Cursor, Claude Code, and OpenAI Codex. Query your notes and docs by reasoning over structure.

## Install

```bash
npx modus-querens --agent cursor --global -y
npx modus-querens --agent claude-code --global -y
npx modus-querens --agent codex --global -y
```

Use `--global` for all projects; omit it to install in the current repo only. Restart your agent after installing.

## Uninstall

```bash
npx modus-querens --uninstall --agent cursor --global -y
```

Same `--agent` and `--global` flags as install. Removes only the skill folders the installer copied (e.g. `~/.cursor/skills/modus-querens/`). It does **not** delete `.modus-querens/` indexes or run logs next to your notes.

## Usage

1. Point the agent at a folder of notes or docs.
2. Ask something like *"Ask my notes how X connects to Y"* or *"Query my knowledge base about …"*.
3. Optional index: `python skills/modus-querens/scripts/build_tree.py <corpus> --out .modus-querens/index`

Runs and indexes are written under `.modus-querens/` next to your corpus.

## License

MIT — see [LICENSE](LICENSE).
