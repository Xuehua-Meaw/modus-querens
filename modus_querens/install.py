"""Install or remove modus-querens in agent-specific skill folders."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

SKILL_NAME = "modus-querens"
AGENT_ORDER = ("cursor", "claude-code", "codex")

SKILL_FILES = (
    "SKILL.md",
    "reference.md",
    "strategy-filebased.md",
    "scripts",
)

AGENTS = {
    "cursor": {
        "label": "Cursor",
        "project_rel": Path(".cursor/skills"),
        "global_rel": Path(".cursor/skills"),
    },
    "claude-code": {
        "label": "Claude Code",
        "project_rel": Path(".claude/skills"),
        "global_rel": Path(".claude/skills"),
    },
    "codex": {
        "label": "Codex",
        "project_rel": Path(".agents/skills"),
        "global_rel": Path(".agents/skills"),
    },
}


def skill_source_root() -> Path:
    return Path(__file__).resolve().parents[1] / "skills" / SKILL_NAME


def destination(agent: str, global_install: bool, cwd: Path) -> Path:
    spec = AGENTS[agent]
    base = Path.home() / spec["global_rel"] if global_install else cwd / spec["project_rel"]
    return base / SKILL_NAME


def legacy_destinations(agent: str, global_install: bool, cwd: Path) -> list[Path]:
    paths: list[Path] = []
    if agent == "cursor":
        base = Path.home() if global_install else cwd
        paths.append(base / ".agents/skills" / SKILL_NAME)
    if agent == "codex" and global_install:
        paths.append(Path.home() / ".codex/skills" / SKILL_NAME)
    return paths


def all_destinations(agent: str, global_install: bool, cwd: Path) -> list[Path]:
    primary = destination(agent, global_install, cwd)
    seen = {primary}
    out = [primary]
    for path in legacy_destinations(agent, global_install, cwd):
        if path not in seen:
            seen.add(path)
            out.append(path)
    return out


def normalize_agent(raw: str) -> str:
    key = raw.lower()
    if key == "claude":
        key = "claude-code"
    if key not in AGENTS:
        allowed = ", ".join(AGENT_ORDER)
        raise SystemExit(f'Unknown agent "{raw}". Use: {allowed}')
    return key


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


def remove_path(path: Path) -> bool:
    if not path.exists():
        return False
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return True


def scope_label(global_install: bool) -> str:
    return "user home (global)" if global_install else "this project"


def agent_line(agent: str, global_install: bool, cwd: Path) -> str:
    spec = AGENTS[agent]
    rel = f"~/{spec['global_rel']}" if global_install else str(spec["project_rel"])
    installed = "installed" if destination(agent, global_install, cwd).exists() else "not installed"
    return f"{spec['label']:<12} {rel}/{SKILL_NAME}  ({installed})"


def pick_agents(global_install: bool, cwd: Path) -> list[str]:
    print(f"\nPick agents for {scope_label(global_install)}:\n")
    for index, agent in enumerate(AGENT_ORDER, start=1):
        print(f"  {index}. {agent_line(agent, global_install, cwd)}")
    print('\nEnter numbers (e.g. 1 3), "all", or q to cancel:')

    if not sys.stdin.isatty():
        raise SystemExit(
            "Non-interactive shell: pass agent names, e.g. modus-querens install cursor codex"
        )

    answer = input("> ").strip().lower()
    if not answer or answer == "q":
        return []
    if answer == "all":
        return list(AGENT_ORDER)

    picks: list[str] = []
    for part in answer.replace(",", " ").split():
        if not part.isdigit():
            continue
        index = int(part)
        if 1 <= index <= len(AGENT_ORDER):
            picks.append(AGENT_ORDER[index - 1])
    if not picks:
        raise SystemExit("No valid selection.")
    return list(dict.fromkeys(picks))


def resolve_agents_for_install(args: argparse.Namespace, cwd: Path) -> list[str]:
    if args.agents:
        return args.agents
    if args.global_install:
        existing = [agent for agent in AGENT_ORDER if destination(agent, True, cwd).exists()]
        if existing:
            return existing
    return pick_agents(args.global_install, cwd)


def resolve_agents_for_uninstall(args: argparse.Namespace) -> list[str]:
    if args.agents:
        return args.agents
    return list(AGENT_ORDER)


def run_install(args: argparse.Namespace, cwd: Path) -> int:
    agents = resolve_agents_for_install(args, cwd)
    if not agents:
        print("Nothing selected.")
        return 0

    source = skill_source_root()
    print(f"\nInstalling to {scope_label(args.global_install)}:")
    for agent in agents:
        dest = destination(agent, args.global_install, cwd)
        dest.parent.mkdir(parents=True, exist_ok=True)
        copy_skill(source, dest)
        print(f"  installed {AGENTS[agent]['label']} → {dest}")
    return 0


def run_uninstall(args: argparse.Namespace, cwd: Path) -> int:
    agents = resolve_agents_for_uninstall(args)
    print(f"\nRemoving from {scope_label(args.global_install)}:")
    for agent in agents:
        removed_any = False
        for path in all_destinations(agent, args.global_install, cwd):
            if remove_path(path):
                print(f"  removed {path}")
                removed_any = True
        if not removed_any:
            print(f"  - {AGENTS[agent]['label']} — not found")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="modus-querens",
        description="Install or remove Modus Querens for coding agents.",
    )
    p.add_argument(
        "command",
        nargs="?",
        choices=("install", "uninstall"),
        default="install",
        help="install (default) or uninstall",
    )
    p.add_argument(
        "-g",
        "--global",
        dest="global_install",
        action="store_true",
        help="User home skill dirs instead of current project",
    )
    p.add_argument(
        "agents",
        nargs="*",
        help="cursor, claude-code, codex (optional; uninstall defaults to all)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.agents = [normalize_agent(name) for name in args.agents]
    cwd = Path.cwd()

    if args.command == "uninstall":
        return run_uninstall(args, cwd)
    return run_install(args, cwd)


if __name__ == "__main__":
    raise SystemExit(main())
