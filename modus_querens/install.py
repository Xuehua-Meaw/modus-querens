"""Copy modus-querens into agent-specific skill folders (uv / pip entrypoint)."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

SKILL_NAME = "modus-querens"
SKILL_FILES = (
    "SKILL.md",
    "reference.md",
    "strategy-filebased.md",
    "scripts",
)

AGENTS = {
    "cursor": {
        "label": "Cursor",
        "project": Path(".cursor/skills"),
        "global": Path.home() / ".cursor" / "skills",
    },
    "claude-code": {
        "label": "Claude Code",
        "project": Path(".claude/skills"),
        "global": Path.home() / ".claude" / "skills",
    },
    "claude": {
        "label": "Claude Code",
        "project": Path(".claude/skills"),
        "global": Path.home() / ".claude" / "skills",
    },
    "codex": {
        "label": "OpenAI Codex",
        "project": Path(".agents/skills"),
        "global": Path.home() / ".codex" / "skills",
    },
}


def skill_source_root() -> Path:
    # modus_querens/install.py -> repo root -> skills/modus-querens
    return Path(__file__).resolve().parents[1] / "skills" / SKILL_NAME


def copy_skill(source: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for name in SKILL_FILES:
        src = source / name
        if not src.exists():
            raise FileNotFoundError(f"Missing skill file: {src}")
        target = dest / name
        if src.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(src, target)
        else:
            shutil.copy2(src, target)


def destinations(agent: str, global_install: bool, cwd: Path) -> list[Path]:
    spec = AGENTS[agent]
    primary_base = spec["global"] if global_install else cwd / spec["project"]
    dests = [primary_base / SKILL_NAME]

    if agent == "cursor":
        agents_base = (
            Path.home() / ".agents" / "skills"
            if global_install
            else cwd / ".agents" / "skills"
        )
        alt = agents_base / SKILL_NAME
        if alt not in dests:
            dests.append(alt)

    return dests


def normalize_agents(raw: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        key = "claude-code" if item == "claude" else item
        if key not in AGENTS:
            allowed = ", ".join(k for k in AGENTS if k != "claude")
            raise SystemExit(f'Unknown agent "{item}". Use: {allowed}')
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="modus-querens",
        description="Install Modus Querens for specific coding agents (not all platforms).",
    )
    p.add_argument(
        "-a",
        "--agent",
        action="append",
        required=True,
        choices=["cursor", "claude-code", "claude", "codex"],
        help="Target agent (repeatable)",
    )
    p.add_argument(
        "-g",
        "--global",
        dest="global_install",
        action="store_true",
        help="Install to user home",
    )
    p.add_argument("-y", "--yes", action="store_true", help="Apply without extra prompt")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    agents = normalize_agents(args.agent)
    source = skill_source_root()
    cwd = Path.cwd()
    plan = []
    for agent in agents:
        spec = AGENTS[agent]
        for dest in destinations(agent, args.global_install, cwd):
            plan.append((spec["label"], dest))

    print("Modus Querens install plan:")
    for label, dest in plan:
        print(f"  • {label} → {dest}")

    if not args.yes:
        print("\nRe-run with -y to apply.", file=sys.stderr)
        return 0

    for _, dest in plan:
        copy_skill(source, dest)
        print(f"Installed → {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
