/** Restrict probe reports and traces to body-free local JSONL files inside the repository. */
import { mkdir, writeFile } from "node:fs/promises";
import { isAbsolute, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

export type SafeArtifactPath = {
  relative: string;
  absolute: string;
};

export function getRepositoryRoot(): string {
  return fileURLToPath(new URL("../../../", import.meta.url));
}

export function defaultTraceRelativePath(now: Date = new Date(Date.now())): string {
  const stamp = now.toISOString().slice(0, 19).replace(/:/g, "-") + "Z";
  return `backend/var/probes/${stamp}.jsonl`;
}

function insideRepository(repoRoot: string, absolutePath: string): boolean {
  const root = resolve(repoRoot);
  const candidate = resolve(absolutePath);
  const fromRoot = relative(root, candidate);
  return fromRoot === "" || (!fromRoot.startsWith(`..${sep}`) && fromRoot !== ".." && !isAbsolute(fromRoot));
}

function forbiddenRelativePath(relativePath: string): boolean {
  const protectedPrefixes = [
    ".git/",
    ".github/",
    "config/",
    "corpus/",
    "docs/",
    "frontend/",
    "state/",
    "backend/idhazh/",
    "backend/models/",
    "backend/bin/",
    "backend/utilities/",
    "backend/var/evidence/",
    "backend/var/council/",
    "backend/tests/",
    "services/feed-ingest-plan/",
    "services/host-probes/",
    "packages/ledger-file-writer/",
  ];
  return protectedPrefixes.some(prefix => relativePath.startsWith(prefix));
}

export function resolveSafeArtifactPath(repoRootRaw: string, raw: string | null, now: Date = new Date(Date.now())): SafeArtifactPath {
  const repoRoot = resolve(repoRootRaw);
  const value = raw ?? defaultTraceRelativePath(now);
  if (!value || value.includes("\0")) throw new Error("Artifact path must be a nonempty local path");

  const windowsAbsolute = /^[A-Za-z]:[\\/]/.test(value) || /^\\\\[^\\]+/.test(value);
  const posixAbsolute = value.startsWith("/");
  const absoluteInput = posixAbsolute || windowsAbsolute || isAbsolute(value);
  let absolute: string;
  let relativePath: string;

  if (absoluteInput) {
    absolute = resolve(value);
  } else {
    if (value.includes("\\") || value.includes("..")) {
      throw new Error("Artifact path must use relative POSIX segments without parent traversal");
    }
    const segments = value.replace(/^\.\//, "").split("/");
    if (segments.some(segment => !segment || segment === "." || segment === "..")) {
      throw new Error("Artifact path must be a valid relative POSIX path");
    }
    const normalized = segments.join("/");
    absolute = resolve(repoRoot, ...normalized.split("/"));
  }

  if (!insideRepository(repoRoot, absolute)) {
    throw new Error("Artifact path must stay inside the repository");
  }
  relativePath = relative(repoRoot, absolute).replace(/\\/g, "/");
  if (!relativePath || forbiddenRelativePath(relativePath)) {
    throw new Error("Artifact path would write outside the allowed probe artifact area or source area");
  }
  if (!relativePath.toLowerCase().endsWith(".jsonl")) {
    throw new Error("Report and trace paths must use the .jsonl extension");
  }
  return { relative: relativePath, absolute };
}

export async function writeJsonLines(path: string, lines: readonly string[]): Promise<void> {
  await mkdir(join(path, ".."), { recursive: true });
  const body = lines.length ? `${lines.join("\n")}\n` : "";
  await writeFile(path, body, "utf8");
}
