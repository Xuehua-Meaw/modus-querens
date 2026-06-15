#!/usr/bin/env node
/**
 * Install or remove modus-querens in agent-specific skill folders.
 */
import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { createInterface } from "node:readline";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { stdin as input, stdout as output } from "node:process";

const SKILL_NAME = "modus-querens";

const AGENT_ORDER = ["cursor", "claude-code", "codex"];

/** Canonical paths from each agent's docs (one folder per agent per scope). */
const AGENTS = {
  cursor: {
    label: "Cursor",
    projectRel: ".cursor/skills",
    globalRel: ".cursor/skills",
  },
  "claude-code": {
    label: "Claude Code",
    projectRel: ".claude/skills",
    globalRel: ".claude/skills",
  },
  codex: {
    label: "Codex",
    projectRel: ".agents/skills",
    globalRel: ".agents/skills",
  },
};

/** Older installs / cross-compat paths — removed on uninstall only. */
const LEGACY_DESTS = {
  cursor: [
    (global, cwd) =>
      join(
        global ? homedir() : cwd,
        ".agents/skills",
        SKILL_NAME,
      ),
  ],
  codex: [
    (global, cwd) =>
      join(
        global ? homedir() : cwd,
        ".codex/skills",
        SKILL_NAME,
      ),
  ],
};

const SKILL_FILES = [
  "SKILL.md",
  "reference.md",
  "strategy-filebased.md",
  "scripts",
];

function usage() {
  console.log(`modus-querens — install or remove this skill for coding agents

Usage:
  npx modus-querens install [-g] [cursor|claude-code|codex ...]
  npx modus-querens uninstall [-g] [cursor|claude-code|codex ...]

Scope:
  (default)   Current project — .cursor/skills, .claude/skills, .agents/skills
  -g, --global   Your user home — ~/.cursor/skills, ~/.claude/skills, ~/.agents/skills

Behavior:
  install              Pick agents with arrow keys + Space, Enter to confirm
  install -g           Update global installs that already exist; if none, pick agents
  uninstall            Remove from all agents in the current project
  uninstall -g         Remove from all agents in your user home
  uninstall cursor     Remove only from named agents

Does not delete .modus-querens/ indexes or run logs next to your notes.
`);
}

function skillSourceRoot() {
  const here = dirname(fileURLToPath(import.meta.url));
  return resolve(here, "..", "skills", SKILL_NAME);
}

function destination(agent, global, cwd) {
  const spec = AGENTS[agent];
  const base = global
    ? join(homedir(), spec.globalRel)
    : join(cwd, spec.projectRel);
  return join(base, SKILL_NAME);
}

function legacyDestinations(agent, global, cwd) {
  const makers = LEGACY_DESTS[agent] ?? [];
  return makers.map((make) => make(global, cwd));
}

function allDestinations(agent, global, cwd) {
  const primary = destination(agent, global, cwd);
  const legacy = legacyDestinations(agent, global, cwd);
  return [...new Set([primary, ...legacy])];
}

function isInstalled(agent, global, cwd) {
  return allDestinations(agent, global, cwd).some((path) => existsSync(path));
}

function normalizeAgent(raw) {
  const key = raw.toLowerCase();
  if (key === "claude") return "claude-code";
  if (!AGENTS[key]) {
    throw new Error(
      `Unknown agent "${raw}". Use: ${AGENT_ORDER.join(", ")}`,
    );
  }
  return key;
}

function parseArgs(argv) {
  let command = null;
  let global = false;
  const agents = [];

  for (const arg of argv) {
    if (arg === "-h" || arg === "--help") return { help: true };
    if (arg === "-g" || arg === "--global") {
      global = true;
      continue;
    }
    if (arg === "install" || arg === "uninstall") {
      if (command) throw new Error(`Duplicate command: ${arg}`);
      command = arg;
      continue;
    }
    if (arg.startsWith("-")) {
      throw new Error(`Unknown option: ${arg}`);
    }
    agents.push(normalizeAgent(arg));
  }

  if (!command) command = "install";
  return { command, global, agents: [...new Set(agents)] };
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

function removePath(path) {
  if (!existsSync(path)) return false;
  rmSync(path, { recursive: true, force: true });
  return true;
}

function scopeLabel(global) {
  return global ? "user home (global)" : "this project";
}

function agentLine(agent, global, cwd) {
  const spec = AGENTS[agent];
  const rel = global ? `~/${spec.globalRel}` : spec.projectRel;
  const mark = isInstalled(agent, global, cwd) ? "installed" : "not installed";
  return `${spec.label.padEnd(12)} ${rel}/${SKILL_NAME}  (${mark})`;
}

function renderPicker(global, cwd, cursor, selected) {
  const lines = [
    `\nPick agents for ${scopeLabel(global)}:`,
    "  Up/Down move · Space toggle · Enter confirm · q quit\n",
  ];
  AGENT_ORDER.forEach((agent, index) => {
    const pointer = index === cursor ? ">" : " ";
    const box = selected[index] ? "[x]" : "[ ]";
    lines.push(` ${pointer} ${box} ${agentLine(agent, global, cwd)}`);
  });
  return lines.join("\n");
}

function pickAgents(global, cwd) {
  if (!input.isTTY) {
    throw new Error(
      "Non-interactive shell: pass agent names, e.g. npx modus-querens install cursor codex",
    );
  }

  return new Promise((resolve) => {
    const rl = createInterface({ input, output });
    let cursor = 0;
    const selected = AGENT_ORDER.map((agent) => isInstalled(agent, global, cwd));

    const refresh = () => {
      output.write("\x1B[?25l");
      output.write("\x1B[2J\x1B[H");
      output.write(renderPicker(global, cwd, cursor, selected));
    };

    const cleanup = (result) => {
      input.setRawMode(false);
      input.removeListener("keypress", onKeypress);
      rl.close();
      output.write("\x1B[?25h\n");
      resolve(result);
    };

    const onKeypress = (_str, key) => {
      if (!key) return;
      if (key.ctrl && key.name === "c") {
        cleanup([]);
        return;
      }
      if (key.name === "up") {
        cursor = (cursor - AGENT_ORDER.length + 1) % AGENT_ORDER.length;
        refresh();
        return;
      }
      if (key.name === "down") {
        cursor = (cursor + 1) % AGENT_ORDER.length;
        refresh();
        return;
      }
      if (key.name === "space") {
        selected[cursor] = !selected[cursor];
        refresh();
        return;
      }
      if (key.name === "return") {
        cleanup(AGENT_ORDER.filter((_, index) => selected[index]));
        return;
      }
      if (key.sequence === "q" || key.sequence === "Q") {
        cleanup([]);
      }
    };

    input.setRawMode(true);
    input.on("keypress", onKeypress);
    refresh();
  });
}

async function resolveAgentsForInstall(parsed, cwd) {
  if (parsed.agents.length) return parsed.agents;

  if (parsed.global) {
    const existing = AGENT_ORDER.filter((agent) => isInstalled(agent, true, cwd));
    if (existing.length) return existing;
  }

  return pickAgents(parsed.global, cwd);
}

function resolveAgentsForUninstall(parsed) {
  if (parsed.agents.length) return parsed.agents;
  return [...AGENT_ORDER];
}

async function runInstall(parsed, cwd) {
  const agents = await resolveAgentsForInstall(parsed, cwd);
  if (!agents.length) {
    console.log("Nothing selected.");
    return;
  }

  const sourceRoot = skillSourceRoot();
  console.log(`\nInstalling to ${scopeLabel(parsed.global)}:`);

  for (const agent of agents) {
    const dest = destination(agent, parsed.global, cwd);
    mkdirSync(dirname(dest), { recursive: true });
    copySkill(sourceRoot, dest);
    console.log(`  installed ${AGENTS[agent].label} → ${dest}`);
  }
}

async function runUninstall(parsed, cwd) {
  const agents = resolveAgentsForUninstall(parsed);
  console.log(`\nRemoving from ${scopeLabel(parsed.global)}:`);

  const removedPaths = new Set();

  for (const agent of agents) {
    const paths = allDestinations(agent, parsed.global, cwd);
    let removedAny = false;

    for (const path of paths) {
      if (removedPaths.has(path)) {
        removedAny = true;
        continue;
      }
      if (removePath(path)) {
        removedPaths.add(path);
        console.log(`  removed ${path}`);
        removedAny = true;
      }
    }

    if (!removedAny) {
      console.log(`  - ${AGENTS[agent].label} — not found`);
    }
  }
}

async function main() {
  const parsed = parseArgs(process.argv.slice(2));
  if (parsed.help) {
    usage();
    return;
  }

  const cwd = process.cwd();

  if (parsed.command === "uninstall") {
    await runUninstall(parsed, cwd);
    return;
  }

  if (parsed.command === "install") {
    await runInstall(parsed, cwd);
    return;
  }

  throw new Error(`Unknown command: ${parsed.command}`);
}

main().catch((err) => {
  console.error(err.message ?? err);
  process.exit(1);
});
