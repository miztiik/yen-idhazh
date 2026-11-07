/** How do offline cases load the real model declaration in an isolated config directory? */
import { randomUUID } from "node:crypto";
import { cpSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const repositoryRoot = fileURLToPath(new URL("../../../", import.meta.url));

export type ModelRecordingEntry = Record<string, unknown> & {
  id: string;
  arch: string;
  thinking_kwarg?: string | null;
  thinking_close: string | null;
  chat_template_kwargs: Record<string, unknown>;
  reasoning_delimiters: [string, string] | null;
  request_timeout_minutes: number;
  sampling: Record<string, unknown>;
};
export type RecordedNativeReply = {
  choices: { finish_reason: string; index: number; message: { content: string; reasoning_content?: string } }[];
  usage: { prompt_tokens: number; completion_tokens: number; total_tokens: number };
  timings: {
    prompt_ms: number; predicted_ms: number; prompt_per_second: number; predicted_per_second: number;
    prompt_n?: number; predicted_n?: number;
  };
};

export function readJson<T = Record<string, unknown>>(relativePath: string): T {
  return JSON.parse(readFileSync(path.join(repositoryRoot, relativePath), "utf8")) as T;
}

export async function withConfig<T>(
  run: (root: string, entry: ModelRecordingEntry) => T | Promise<T>,
): Promise<T> {
  const root = path.join(repositoryRoot, "backend", "var", `summary-generator-contract-${randomUUID()}`);
  mkdirSync(root, { recursive: true });
  for (const name of [
    "idhazh.json", "ledgers.json", "sources.json", "taxonomy.json", "watchlist.json",
    "llm_council.json", "appearance.json",
  ]) {
    cpSync(path.join(repositoryRoot, "config", name), path.join(root, name));
  }
  mkdirSync(path.join(root, "summary-generator"));
  for (const name of ["api.json", "workflow.json"]) {
    cpSync(path.join(repositoryRoot, "config", "summary-generator", name),
      path.join(root, "summary-generator", name));
  }
  mkdirSync(path.join(root, "prompts"));
  for (const name of ["generate-summary.txt", "request-json.txt", "analyze-article.txt"]) {
    cpSync(path.join(repositoryRoot, "config", "prompts", name), path.join(root, "prompts", name));
  }
  const council = readJson<{ judge_names: string[] }>("config/llm_council.json");
  mkdirSync(path.join(root, "judges"));
  for (const name of council.judge_names) {
    cpSync(path.join(repositoryRoot, "config", "judges", `${name}.json`), path.join(root, "judges", `${name}.json`));
  }
  const pointer = readJson<{ models_file: string }>("config/idhazh.json");
  const entry = readJson<{ summarizer: ModelRecordingEntry }>(path.join("config", pointer.models_file)).summarizer;
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

export function writeEntry(root: string, entry: ModelRecordingEntry) {
  writeFileSync(
    path.join(root, "models", "independent-substitution.json"),
    JSON.stringify({ version: "2026-10-24", summarizer: entry }),
  );
}
