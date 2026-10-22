/** Builds ledger destinations and confirms their parents remain under the output root. */
import { mkdir, realpath } from "node:fs/promises";
import { dirname, isAbsolute, relative, resolve, sep } from "node:path";
import type { LedgerPeriod } from "./ledger-types";

export function toRelativePath(root: string, target: string): string {
  const path = relative(root, target);
  if (!path || path === ".." || path.startsWith(`..${sep}`) || isAbsolute(path)) {
    throw new Error(`ledger path escapes output root: ${target}`);
  }
  return path.split(sep).join("/");
}

export async function checkTrustedParent(root: string, target: string): Promise<void> {
  await mkdir(dirname(target), { recursive: true });
  const [rootPath, parentPath] = await Promise.all([realpath(root), realpath(dirname(target))]);
  const fromRoot = relative(rootPath, parentPath);
  if (fromRoot === ".." || fromRoot.startsWith(`..${sep}`) || isAbsolute(fromRoot)) {
    throw new Error(`ledger path resolves outside output root: ${target}`);
  }
}

export function buildRawPath(root: string, prefix: readonly string[], covers: string, file: string): string {
  return resolve(root, "raw", ...prefix, covers.slice(0, 4), covers.slice(5, 7), covers.slice(8, 10), `${file}.parquet`);
}

export function buildCompactPath(
  root: string,
  prefix: readonly string[],
  period: Extract<LedgerPeriod, { tier: "compact" }>,
): string {
  const parts = period.period === "daily"
    ? [period.covers.slice(0, 4), period.covers.slice(5, 7), `${period.covers.slice(8, 10)}.parquet`]
    : period.period === "monthly"
      ? [period.covers.slice(0, 4), `${period.covers.slice(5, 7)}.parquet`]
      : [period.covers, `${period.covers}.parquet`];
  return resolve(root, "compact", ...prefix, period.period, ...parts);
}
