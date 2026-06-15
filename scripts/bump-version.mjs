#!/usr/bin/env node
/**
 * Sync version across package.json, pyproject.toml, and skills/modus-querens/SKILL.md
 *
 * Usage:
 *   node scripts/bump-version.mjs patch
 *   node scripts/bump-version.mjs minor
 *   node scripts/bump-version.mjs major
 *   node scripts/bump-version.mjs 0.1.32
 *   npm run version:patch
 *   npm run version:set -- 0.1.32
 */
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

const TARGETS = [
  {
    path: join(ROOT, "package.json"),
    apply: (text, version) =>
      text.replace(/("version"\s*:\s*")[^"]+(")/, `$1${version}$2`),
  },
  {
    path: join(ROOT, "pyproject.toml"),
    apply: (text, version) =>
      text.replace(/(^\s*version\s*=\s*")[^"]+(")/m, `$1${version}$2`),
  },
  {
    path: join(ROOT, "skills", "modus-querens", "SKILL.md"),
    apply: (text, version) =>
      text.replace(/(^\s*version:\s*")[^"]+(")/m, `$1${version}$2`),
  },
];

function readVersion() {
  const pkg = JSON.parse(readFileSync(join(ROOT, "package.json"), "utf8"));
  if (!pkg.version) throw new Error("package.json has no version field");
  return pkg.version;
}

function parseSemver(version) {
  const match = /^(\d+)\.(\d+)\.(\d+)$/.exec(version);
  if (!match) throw new Error(`Invalid semver: ${version}`);
  return {
    major: Number(match[1]),
    minor: Number(match[2]),
    patch: Number(match[3]),
  };
}

function formatSemver({ major, minor, patch }) {
  return `${major}.${minor}.${patch}`;
}

function bump(current, kind) {
  const parts = parseSemver(current);
  if (kind === "patch") parts.patch += 1;
  else if (kind === "minor") {
    parts.minor += 1;
    parts.patch = 0;
  } else if (kind === "major") {
    parts.major += 1;
    parts.minor = 0;
    parts.patch = 0;
  } else {
    throw new Error(`Unknown bump kind: ${kind}`);
  }
  return formatSemver(parts);
}

function resolveNextVersion(current, arg) {
  if (!arg) return bump(current, "patch");
  if (arg === "patch" || arg === "minor" || arg === "major") {
    return bump(current, arg);
  }
  if (/^\d+\.\d+\.\d+$/.test(arg)) return arg;
  throw new Error(`Usage: bump-version.mjs [patch|minor|major|x.y.z]`);
}

function writeVersion(version) {
  for (const target of TARGETS) {
    const text = readFileSync(target.path, "utf8");
    const next = target.apply(text, version);
    if (next === text) {
      throw new Error(`Could not update version in ${target.path}`);
    }
    writeFileSync(target.path, next, "utf8");
  }
}

function main() {
  const current = readVersion();
  const next = resolveNextVersion(current, process.argv[2]);
  writeVersion(next);
  console.log(`${current} -> ${next}`);
  console.log("Updated: package.json, pyproject.toml, skills/modus-querens/SKILL.md");
}

main();
