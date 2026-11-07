/** How do offline cases load the real model declaration in an isolated config directory? */
import { randomUUID } from "node:crypto";
import { cpSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const repositoryRoot = fileURLToPath(new URL("../../../", import.meta.url));

export function readJson(relativePath: string) {
  return JSON.parse(readFileSync(path.join(repositoryRoot, relativePath), "utf8"));
}

export async function withConfig<T>(
  run: (root: string, entry: Record<string, any>) => T | Promise<T>,
): Promise<T> {
  const root = path.join(repositoryRoot, "backend", "var", `summarizer-contract-${randomUUID()}`);
  mkdirSync(root, { recursive: true });
  for (const name of [
    "idhazh.json", "ledgers.json", "sources.json", "taxonomy.json", "watchlist.json",
    "llm_council.json", "appearance.json",
  ]) {
    cpSync(path.join(repositoryRoot, "config", name), path.join(root, name));
  }
  const council = readJson("config/llm_council.json");
  mkdirSync(path.join(root, "judges"));
  for (const name of council.judge_names) {
    cpSync(path.join(repositoryRoot, "config", "judges", `${name}.json`), path.join(root, "judges", `${name}.json`));
  }
  const pointer = readJson("config/idhazh.json");
  const entry = readJson(path.join("config", pointer.models_file)).summarizer;
  pointer.models_file = "models/independent-substitution.json";
  mkdirSync(path.join(root, "models"));
  writeFileSync(path.join(root, "idhazh.json"), JSON.stringify(pointer));
  writeEntry(root, entry);
  try {
    return await run(root, entry);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
}

export function writeEntry(root: string, entry: Record<string, any>) {
  writeFileSync(
    path.join(root, "models", "independent-substitution.json"),
    JSON.stringify({ version: "2026-10-24", summarizer: entry }),
  );
}
