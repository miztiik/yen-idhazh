/** Write and read bounded native rows without archived Git membership. */
import { join } from "node:path";
import { PlannerLedgerNameSchema, WriterIdentitySchema } from "@idhazh/common-contracts";
import type { WriterIdentity } from "@idhazh/common-contracts";
import { persistLedger, readPlannerParquet } from "@idhazh/ledger-file-writer";
import type { LedgerRegistration, LedgerRowContract, LedgerSettings, PersistLedgerResult } from "@idhazh/ledger-file-writer";

export const settings: LedgerSettings = { format: "parquet", compression_raw: "snappy", compression_compact: "zstd" };
export function registration(name: string): LedgerRegistration {
  const planner = ["discovered-articles", "selected-articles", "rejected-articles", "feed-health-state", "plan-runs"].includes(name);
  return {
    name, family: planner ? "feed-ingest-plan" : name, grain: "raw-and-compact",
    lifecycle_status: "active", prefix: planner ? ["feed-ingest-plan", name] : [name],
  };
}
export function writer(runId: string, attempt = 1, shard = 0): WriterIdentity {
  return WriterIdentitySchema.parse({
    run_id: runId, attempt, job: null, pipeline_name: "plan", task_name: "persist-selected-articles",
    shard, producer: "tests.partition", git_sha: "a".repeat(40),
  });
}
export async function readWritten<T extends object>(
  root: string, ledger: string, day: string, contract: LedgerRowContract<T>, written: PersistLedgerResult,
) {
  if (written.status === "skipped") throw new Error("Fixture ledger was skipped");
  const files = await Promise.all(written.files.map(file => readPlannerParquet(join(root, file.path),
    PlannerLedgerNameSchema.parse(ledger), contract)));
  if (files.some(file => file.envelope.ledger !== ledger || file.envelope.covers !== day)) {
    throw new Error("Completed fixture output differs from its named ledger day");
  }
  return { rows: files.flatMap(file => file.rows) };
}
export async function writeRows<T extends object>(
  root: string, ledger: string, day: string, contract: LedgerRowContract<T>, rows: readonly T[],
  identity: WriterIdentity | null = null,
) {
  return persistLedger({
    ledger, outputRoot: root, ...(identity === null ? {} : { writerContext: identity }), registryEntry: registration(ledger),
    ledgerSettings: settings, rowContract: contract, period: { tier: "raw", covers: day }, rows,
    ...(ledger === "feed-health-state" ? { updatedAt: `${day}T23:59:59.123Z` } : {}),
  });
}
export async function compactRows<T extends object>(
  root: string, ledger: string, day: string, contract: LedgerRowContract<T>, rows: readonly T[],
  period: "daily" | "monthly" | "yearly",
) {
  const covers = day.slice(0, period === "daily" ? 10 : period === "monthly" ? 7 : 4);
  const written = await persistLedger({
    ledger, outputRoot: root, registryEntry: registration(ledger),
    ledgerSettings: settings, rowContract: contract, period: { tier: "compact", period, covers, builtFrom: 1 }, rows,
    ...(ledger === "feed-health-state" ? { updatedAt: `${day}T23:59:59.123Z` } : {}),
  });
  const file = written.files[0];
  return { written, path: file === undefined ? undefined : join(root, file.path) };
}
