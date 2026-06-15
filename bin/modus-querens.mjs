#!/usr/bin/env node
/**
 * Install modus-querens into agent-specific skill folders only (never --all).
 */
import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SKILL_NAME = "modus-querens";

/** Native paths each agent documents for skill discovery. */
const AGENTS = {
  cursor: {
    label: "Cursor",
    project: ".cursor/skills",
    global: join(homedir(), ".cursor", "skills"),
  },
  "claude-code": {
    label: "Claude Code",
    project: ".claude/skills",
    global: join(homedir(), ".claude", "skills"),
  },
  claude: {
    label: "Claude Code",
    project: ".claude/skills",
    global: join(homedir(), ".claude", "skills"),
  },
  codex: {
    label: "OpenAI Codex",
    project: ".agents/skills",
    global: join(homedir(), ".codex", "skills"),
  },
};

const SKILL_FILES = [
  "SKILL.md",
  "reference.md",
  "strategy-filebased.md",
  "scripts",
];

function usage() {
  console.log(`modus-querens — install or remove the skill for specific coding agents

Usage:
  npx modus-querens --agent <agent> [--agent <agent> ...] [options]
  npx modus-querens --uninstall --agent cursor --global -y

Agents (pick one or more; required):
  cursor        Cursor (.cursor/skills/ + .agents/skills/)
  claude-code   Claude Code (.claude/skills/)  alias: claude
  codex         OpenAI Codex (.agents/skills/ project, ~/.codex/skills/ global)

Options:
  -a, --agent <name>   Target agent (repeatable)
  -g, --global         User home skill dirs (default: current project)
  -u, --uninstall      Remove installed skill folders (not .modus-querens/ run data)
  -y, --yes            Skip confirmation
  --copy               Copy files on install (default). Symlinks are not used here.
  -h, --help           Show this help

Examples:
  npx modus-querens --agent cursor --global -y
  npx modus-querens --uninstall --agent cursor --global -y
  npx modus-querens --uninstall --agent claude-code --agent codex --global -y
`);
}

function parseArgs(argv) {
  const agents = [];
  let global = false;
  let yes = false;
  let uninstall = false;

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "-h" || arg === "--help") return { help: true };
    if (arg === "-g" || arg === "--global") {
      global = true;
      continue;
    }
    if (arg === "-u" || arg === "--uninstall") {
      uninstall = true;
      continue;
    }
    if (arg === "-y" || arg === "--yes") {
      yes = true;
      continue;
    }
    if (arg === "--copy") continue;
    if (arg === "-a" || arg === "--agent") {
      const next = argv[++i];
      if (!next) throw new Error("Missing value for --agent");
      agents.push(next.toLowerCase());
      continue;
    }
    if (arg.startsWith("--agent=")) {
      agents.push(arg.slice("--agent=".length).toLowerCase());
      continue;
    }
    throw new Error(`Unknown argument: ${arg}`);
  }

  return { agents, global, yes, uninstall };
}

function copySkill(sourceRoot, destRoot) {
  mkdirSync(destRoot, { recursive: true });
  for (const entry of SKILL_FILES) {
    const src = join(sourceRoot, entry);
    const dest = join(destRoot, entry);
    if (!existsSync(src)) {
      throw new Error(`Missing skill file: ${src}`);
    }
    cpSync(src, dest, { recursive: true, force: true });
  }
}

function removeSkill(destRoot) {
  if (!existsSync(destRoot)) {
    return false;
  }
  rmSync(destRoot, { recursive: true, force: true });
  return true;
}

function skillSourceRoot() {
  const here = dirname(fileURLToPath(import.meta.url));
  return resolve(here, "..", "skills", SKILL_NAME);
}

function destinations(agent, global, cwd) {
  const spec = AGENTS[agent];
  const primaryBase = global ? spec.global : join(cwd, spec.project);
  const dests = [join(primaryBase, SKILL_NAME)];

  if (agent === "cursor") {
    const agentsBase = global
      ? join(homedir(), ".agents", "skills")
      : join(cwd, ".agents", "skills");
    const alt = join(agentsBase, SKILL_NAME);
    if (alt !== dests[0]) dests.push(alt);
  }

  return dests;
}

function normalizeAgents(list) {
  const out = [];
  const seen = new Set();
  for (const raw of list) {
    const key = raw === "claude" ? "claude-code" : raw;
    if (!AGENTS[key]) {
      throw new Error(
        `Unknown agent "${raw}". Use: ${Object.keys(AGENTS).filter((k) => k !== "claude").join(", ")}`,
      );
    }
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(key);
  }
  return out;
}

async function main() {
  const parsed = parseArgs(process.argv.slice(2));
  if (parsed.help) {
    usage();
    return;
  }

  if (!parsed.agents?.length) {
    console.error("Error: pass at least one --agent (cursor, claude-code, codex).\n");
    usage();
    process.exit(1);
  }

  const agents = normalizeAgents(parsed.agents);
  const sourceRoot = skillSourceRoot();
  const cwd = process.cwd();
  const installs = [];
  for (const agent of agents) {
    const spec = AGENTS[agent];
    for (const dest of destinations(agent, parsed.global, cwd)) {
      installs.push({ agent, label: spec.label, dest });
    }
  }

  const action = parsed.uninstall ? "uninstall" : "install";
  console.log(`Modus Querens ${action} plan:`);
  for (const row of installs) {
    console.log(`  • ${row.label} → ${row.dest}`);
  }

  if (!parsed.yes && process.stdin.isTTY) {
    console.log("\nRe-run with -y to apply.");
    process.exit(0);
  }

  if (parsed.uninstall) {
    for (const row of installs) {
      if (removeSkill(row.dest)) {
        console.log(`Removed → ${row.dest}`);
      } else {
        console.log(`Skipped (not found) → ${row.dest}`);
      }
    }
    return;
  }

  for (const row of installs) {
    mkdirSync(dirname(row.dest), { recursive: true });
    copySkill(sourceRoot, row.dest);
    console.log(`Installed → ${row.dest}`);
  }
}

main().catch((err) => {
  console.error(err.message ?? err);
  process.exit(1);
});
