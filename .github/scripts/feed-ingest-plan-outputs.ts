/** Which validated identities, paths and worker counts may the isolated workflow use? */
import { randomUUID, createHash } from "node:crypto";
import { appendFile } from "node:fs/promises";
import { posix } from "node:path";
import {
  COMPACT_INDEX_VERSION, RAW_DAY_INDEX_VERSION, CompactIndexSchema, DateStampSchema, PartitionAssignmentSchema, PositiveCountSchema,
  RawDayIndexSchema, RunIdSchema, Sha256Schema,
} from "../../packages/common-contracts/src/index";
import type { CompactIndex, RawDayIndex } from "../../packages/common-contracts/src/index";
import type { LedgerRegistration, PersistLedgerResult } from "../../packages/ledger-file-writer/src/index";
import type { summarizePlan } from "../../services/feed-ingest-plan/src/run-feed-plan";
import { UtcInstantSchema } from "../../services/feed-ingest-plan/src/screen-article-candidates/seen-evidence";
import { RelativePathSchema } from "../../services/feed-ingest-plan/src/config/service-settings";
import { validateLedgerFilePath, verifyLedgerReceipt } from "./feed-ingest-plan-verification";

type PlanSummary = ReturnType<typeof summarizePlan>;
type Registrations = Readonly<{
  dispatches: LedgerRegistration; rejections: LedgerRegistration; selections: LedgerRegistration; seen: LedgerRegistration;
  assessments: LedgerRegistration; diversity: LedgerRegistration;
}>;

function paths(result: PersistLedgerResult, entry: LedgerRegistration): string[] {
  if (result === undefined || !Array.isArray(result.files)) throw new Error(`${entry.name}.files is required`);
  if (result.status === "empty" && result.files.length === 0) return [];
  if (result.status !== "written" || result.files.length === 0) throw new Error(`${entry.name}.status has no durable file evidence`);
  return result.files.map(file => {
    PositiveCountSchema.parse(file.row_count);
    Sha256Schema.parse(file.content_sha256);
    return validateLedgerFilePath(file.path, file.file_id, file.covers, entry);
  });
}

export function createExecutionOutputs(summary: PlanSummary, registrations: Registrations): Record<string, string> {
  if (summary.status !== "dispatches_persisted_audit_pending" || summary.audited_complete !== false
    || summary.audit.status !== (summary.metrics === undefined ? "unavailable" : "assessment_diversity_recorded_audit_pending")) {
    throw new Error("audited_complete requires durable recorder evidence; no complete audit is supported by this runner");
  }
  const runId = RunIdSchema.parse(summary.run_id);
  const day = DateStampSchema.parse(summary.date);
  const observedAt = UtcInstantSchema.parse(summary.observed_at);
  if (day !== observedAt.slice(0, 10)) throw new Error("date differs from the observed UTC instant");
  const count = PositiveCountSchema.parse(summary.dispatch_count);
  PartitionAssignmentSchema.parse({ strategy: summary.strategy, worker_assignment: 0, dispatch_count: count });
  if (summary.request.shards !== count || summary.request.partition_strategy !== summary.strategy) {
    throw new Error("request differs from the resolved worker count or strategy");
  }
  if (registrations.dispatches.name !== "dispatches" || registrations.rejections.name !== "rejections"
    || registrations.selections.name !== "editorial-selections" || registrations.seen.name !== "seen") {
    throw new Error("registrations name the wrong ledgers");
  }
  const candidates = summary.selected_candidate_ids.map(id => Sha256Schema.parse(id));
  if (new Set(candidates).size !== candidates.length || summary.assignments.length !== candidates.length) {
    throw new Error("selected_candidate_ids and assignments must identify the same distinct articles");
  }
  const assigned = new Set<string>();
  for (const assignment of summary.assignments) {
    const id = Sha256Schema.parse(assignment.candidate_id);
    const partition = PartitionAssignmentSchema.parse(assignment.partition);
    if (!candidates.includes(id) || assigned.has(id) || partition.dispatch_count !== count
      || partition.strategy !== summary.strategy) throw new Error("assignments differ from the resolved selection or worker count");
    assigned.add(id);
  }
  if (summary.strategy === "none" && count !== 1) throw new Error("dispatch_count must be one for strategy none");
  const dispatches = paths(summary.files.dispatches, registrations.dispatches);
  const selections = paths(summary.files.selections, registrations.selections);
  const seen = paths(summary.files.seen, registrations.seen);
  const rejections = [
    ...paths(summary.files.harvest_rejections, registrations.rejections),
    ...paths(summary.files.screening_rejections, registrations.rejections),
    ...paths(summary.files.curation_rejections, registrations.rejections),
  ];
  const metrics: Record<string, string> = {};
  const metricPaths: string[] = [];
  if (summary.metrics !== undefined) {
    if (summary.metrics.audited_complete !== false || summary.metrics.status !== "assessment_diversity_recorded_audit_pending") {
      throw new Error("metrics.status cannot claim complete audit");
    }
    for (const [key, ledger] of [["assessments", "article-assessments"], ["diversity", "diversity"]] as const) {
      if (registrations[key].name !== ledger) throw new Error(`registrations.${key} names the wrong ledger`);
      const files = summary.metrics.files[key];
      const filePaths = paths(files, registrations[key]);
      verifyLedgerReceipt(ledger, files, summary.metrics.receipts[key]);
      metrics[`${key}_files`] = JSON.stringify(filePaths);
      metricPaths.push(...filePaths);
    }
    metrics.metrics_status = summary.metrics.status;
  }
  const all = [...dispatches, ...selections, ...rejections, ...seen, ...metricPaths];
  if (new Set(all).size !== all.length) throw new Error("files.path occurs more than once");
  if (summary.files.dispatches.files.reduce((total, file) => total + file.row_count, 0) !== candidates.length
    || summary.files.selections.files.reduce((total, file) => total + file.row_count, 0) !== candidates.length) {
    throw new Error("files.row_count differs from selected_candidate_ids");
  }
  return {
    status: summary.status, audited_complete: "false", run_id: runId, date: day,
    dispatch_count: String(count),
    matrix: JSON.stringify({ include: Array.from({ length: count }, (_, worker_assignment) => ({ worker_assignment })) }),
    dispatch_files: JSON.stringify(dispatches), rejection_files: JSON.stringify(rejections),
    selection_files: JSON.stringify(selections), seen_files: JSON.stringify(seen),
    first_sight_absence_proof: summary.first_sight.absence_proof,
    ...metrics,
  };
}

export async function writeGitHubOutputs(path: string, outputs: Readonly<Record<string, string>>): Promise<void> {
  if (path.length === 0) throw new Error("GITHUB_OUTPUT is required");
  const lines = Object.entries(outputs).map(([key, value]) => {
    if (!/^[a-z][a-z0-9_]*$/.test(key) || value.includes("\0")) throw new Error("Invalid GitHub output key or NUL value");
    let delimiter: string;
    do { delimiter = `output_${randomUUID().replaceAll("-", "")}`; } while (value.includes(delimiter));
    return `${key}<<${delimiter}\n${value.replaceAll("\r\n", "\n").replaceAll("\r", "\n")}\n${delimiter}\n`;
  });
  await appendFile(path, lines.join(""), "utf8");
}

export function sparseCheckoutPath(path: string): string {
  if (/[\u0000-\u001f\u007f]/.test(path)) throw new Error("history.path must not contain control characters");
  RelativePathSchema.parse(path);
  return `/${path.replace(/[\\*?[\]!#]/g, character => `\\${character}`)}`;
}

function utcDays(observedAt: string, count: number): string[] {
  const instant = UtcInstantSchema.parse(observedAt);
  const midnight = Date.parse(`${instant.slice(0, 10)}T00:00:00Z`);
  // A UTC day is a protocol unit of 86,400,000 milliseconds, not a tuning control.
  return Array.from({ length: count }, (_, offset) => new Date(midnight - offset * 86_400_000).toISOString().slice(0, 10));
}

export function historyDays(observedAt: string, rollingDays: number, overlapDays: readonly number[]): string[] {
  const rolling = PositiveCountSchema.parse(rollingDays);
  const span = rolling + Math.max(rolling, ...overlapDays.map(value => PositiveCountSchema.parse(value)));
  return utcDays(observedAt, span);
}

export function createSeenDayInputs(prefix: readonly string[], days: readonly string[]) {
  const indexes = historyIndexPaths(prefix, []);
  const base = prefix.join("/");
  return days.map(day => ({
    day: DateStampSchema.parse(day),
    indexes: { yearly: indexes[0]!, monthly: indexes[1]!, daily: indexes[2]! },
    raw_index: `state/raw/${base}/${day.replaceAll("-", "/")}/index.json`,
  }));
}

export function historyIndexPaths(prefix: readonly string[], days: readonly string[]): string[] {
  if (prefix.length === 0 || prefix.some(piece => !/^[a-z0-9][a-z0-9-]*$/.test(piece))) {
    throw new Error("history.prefix must contain directory identifiers");
  }
  const base = prefix.join("/");
  return [
    ...(["yearly", "monthly", "daily"] as const).map(period => `state/compact/${base}/index/${period}.json`),
    ...days.map(day => `state/raw/${base}/${DateStampSchema.parse(day).replaceAll("-", "/")}/index.json`),
  ];
}

export function resolveHistoryInventory(input: Readonly<{
  ledger: CompactIndex["ledger"]; prefix: readonly string[]; days: readonly string[];
  compact: readonly CompactIndex[]; raw: readonly RawDayIndex[];
  indexes?: Readonly<Partial<Record<CompactIndex["period"], string>>>;
  rawIndexes?: Readonly<Record<string, string>>;
}>): string[] {
  const defaults = historyIndexPaths(input.prefix, []);
  const indexes = { yearly: defaults[0]!, monthly: defaults[1]!, daily: defaults[2]!, ...input.indexes };
  const rawIndex = (day: string) => input.rawIndexes?.[day]
    ?? `state/raw/${input.prefix.join("/")}/${day.replaceAll("-", "/")}/index.json`;
  const inventory = new Set([...Object.values(indexes), ...input.days.map(rawIndex)]);
  for (const path of inventory) RelativePathSchema.parse(path);
  const compact = input.compact.map(value => CompactIndexSchema.parse(value));
  const raw = input.raw.map(value => RawDayIndexSchema.parse(value));
  if (compact.some(index => index.version > COMPACT_INDEX_VERSION) || raw.some(index => index.version > RAW_DAY_INDEX_VERSION)) {
    throw new Error("history.index.version is newer than the declared reader");
  }
  if (compact.some(index => index.ledger !== input.ledger) || raw.some(index => index.ledger !== input.ledger)
    || new Set(compact.map(index => index.period)).size !== compact.length
    || new Set(raw.map(index => index.date)).size !== raw.length) {
    throw new Error("history indexes repeat or belong to another ledger");
  }
  for (const day of input.days) {
    DateStampSchema.parse(day);
    const year = compact.find(index => index.period === "yearly");
    if (year?.expired_through !== null && year?.expired_through !== undefined && day.slice(0, 4) <= year.expired_through) continue;
    const match = (["yearly", "monthly", "daily"] as const).map(period => {
      const index = compact.find(index => index.period === period);
      const covers = period === "yearly" ? day.slice(0, 4) : period === "monthly" ? day.slice(0, 7) : day;
      return { period, entry: index?.entries.find(entry => entry.covers === covers) };
    }).find(held => held.entry !== undefined);
    if (match?.entry !== undefined) {
      const entry = match.entry;
      const periodPath = match.period === "yearly" ? `${entry.covers}/${entry.covers}` : entry.covers.replaceAll("-", "/");
      inventory.add(`${posix.dirname(posix.dirname(indexes[match.period]))}/${match.period}/${periodPath}.parquet`);
      continue;
    }
    const index = raw.find(index => index.date === day);
    if (index === undefined) continue;
    const digest = createHash("sha256").update(index.files.join("\n"), "utf8").digest("hex");
    if (digest !== index.content_sha256) throw new Error("history.raw.content_sha256 differs from its filename list");
    for (const name of index.files) inventory.add(`${posix.dirname(rawIndex(day))}/${name}`);
  }
  return [...inventory];
}
