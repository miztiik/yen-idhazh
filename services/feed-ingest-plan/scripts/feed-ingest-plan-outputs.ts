/** Expose only exact current planner metadata paths and bounded native history inputs. */
import { randomUUID, createHash } from "node:crypto";
import { appendFile } from "node:fs/promises";
import { posix } from "node:path";
import {
  COMPACT_INDEX_VERSION, RAW_DAY_INDEX_VERSION, CompactIndexSchema, DateStampSchema, PlannerLedgerNameSchema, RawDayIndexSchema,
} from "../../../packages/common-contracts/src/index";
import type { CompactIndex } from "../../../packages/common-contracts/src/index";
import type { LedgerRegistration } from "../../../packages/ledger-file-writer/src/index";
import { RelativePathSchema, SeenDayInputSchema } from "../src/config/service-settings";
import type { SeenDayInput } from "../src/config/service-settings";
import { validateLedgerFilePath } from "./feed-ingest-plan-verification";
import { PlanResponseSchema } from "../src/api/plan-response.schema";
import { LedgerHistoryReadError } from "../src/read-ledger-history/ledger-history-error";

export function createExecutionOutputs(raw: unknown, registrations: {
  discovered_articles: LedgerRegistration; selected_articles: LedgerRegistration;
  feed_health_state: LedgerRegistration; plan_runs: LedgerRegistration;
}): Record<string, string> {
  const summary = PlanResponseSchema.parse(raw);
  const paths: string[] = [];
  for (const key of ["discovered_articles", "selected_articles", "feed_health_state", "plan_runs"] as const) {
    const result = summary.files[key];
    if (result === undefined) {
      if (summary.planning_complete) throw new Error("Completed run lacks an explicit planner ledger result");
      continue;
    }
    for (const file of result.files) {
      paths.push(validateLedgerFilePath(file.path, file.file_id, file.covers, registrations[key]));
    }
  }
  if (new Set(paths).size !== paths.length || summary.planning_complete !== (summary.status === "completed")) throw new Error("Planner output identity or completion differs");
  if (summary.files.plan_runs?.status !== "written") throw new Error("Planner output lacks its native run outcome");
  return {
    status: summary.status, planning_complete: String(summary.planning_complete), run_id: summary.run_id, date: summary.date,
    selected_count: String(summary.selected_count), dispatch_count: String(summary.dispatch_count),
    matrix: JSON.stringify({ include: Array.from({ length: summary.dispatch_count }, (_, worker_assignment) => ({ worker_assignment })) }),
    current_run_files: JSON.stringify(paths),
    selected_articles_artifact: summary.selected_articles_artifact === null ? "" : RelativePathSchema.parse(summary.selected_articles_artifact),
  };
}
export async function writeGitHubOutputs(path: string, outputs: Readonly<Record<string, string>>) {
  if (!path) throw new Error("Output file is required");
  const lines = Object.entries(outputs).map(([key, value]) => {
    if (!/^[a-z][a-z0-9_]*$/.test(key) || value.includes("\0")) throw new Error("Invalid output key or NUL value");
    let delimiter: string;
    do { delimiter = `output_${randomUUID().replaceAll("-", "")}`; } while (value.includes(delimiter));
    return `${key}<<${delimiter}\n${value.replaceAll("\r\n", "\n").replaceAll("\r", "\n")}\n${delimiter}\n`;
  });
  await appendFile(path, lines.join(""), "utf8");
}
export function sparseCheckoutPath(path: string) {
  if (/[\u0000-\u001f\u007f]/.test(path)) throw new Error("History path contains a control character");
  RelativePathSchema.parse(path);
  return `/${path.replace(/[\\*?[\]!#]/g, character => `\\${character}`)}`;
}
export function createSeenDayInputs(prefix: readonly string[], days: readonly string[]) {
  const indexes = resolveHistoryIndexes(prefix);
  return days.map(day => ({
    day: DateStampSchema.parse(day), indexes,
    ...(prefix[0] === "feed-ingest-plan" ? {} : {
      raw_index: `state/raw/${prefix.join("/")}/${day.replaceAll("-", "/")}/index.json`,
    }),
  }));
}
export function completeHistoryDayInputs(prefix: readonly string[], required: readonly string[], authored: readonly SeenDayInput[], name: string): SeenDayInput[] {
  const byDay = new Map<string, SeenDayInput>();
  for (const [index, raw] of authored.entries()) {
    const day = SeenDayInputSchema.parse(raw);
    if ((index > 0 && day.day <= authored[index - 1]!.day) || !required.includes(day.day)) throw new Error(`${name} requires distinct ascending configured UTC days`);
    byDay.set(day.day, day);
  }
  return createSeenDayInputs(prefix, required).map(day => byDay.get(day.day) ?? day);
}
export function resolveHistoryIndexes(prefix: readonly string[], overrides?: SeenDayInput["indexes"]) {
  const defaults = historyIndexPaths(prefix, []);
  return { yearly: overrides?.yearly ?? defaults[0]!, monthly: overrides?.monthly ?? defaults[1]!,
    daily: overrides?.daily ?? defaults[2]! };
}
export function historyIndexPaths(prefix: readonly string[], days: readonly string[]) {
  if (prefix.length === 0 || prefix.some(piece => !/^[a-z0-9][a-z0-9-]*$/.test(piece))) throw new Error("History prefix requires directory identifiers");
  return [
    ...(["yearly", "monthly", "daily"] as const).map(period => `state/compact/${prefix.join("/")}/index/${period}.json`),
    ...(prefix[0] === "feed-ingest-plan" ? [] : days.map(day =>
      `state/raw/${prefix.join("/")}/${DateStampSchema.parse(day).replaceAll("-", "/")}/index.json`)),
  ];
}
export function resolveHistoryInventory(input: {
  ledger: CompactIndex["ledger"]; prefix: readonly string[]; days: readonly string[];
  compact: readonly CompactIndex[]; rawFiles?: readonly string[];
  raw?: readonly unknown[]; rawIndexes?: Readonly<Record<string, string>>;
  indexes?: SeenDayInput["indexes"];
}) {
  const indexes = resolveHistoryIndexes(input.prefix, input.indexes);
  const paths = new Set(Object.values(indexes));
  const planner = PlannerLedgerNameSchema.safeParse(input.ledger).success;
  const rawIndex = (day: string) => input.rawIndexes?.[day]
    ?? `state/raw/${input.prefix.join("/")}/${day.replaceAll("-", "/")}/index.json`;
  const raw = (input.raw ?? []).map(value => RawDayIndexSchema.parse(value));
  const compact = input.compact.map(value => CompactIndexSchema.parse(value));
  if (compact.some(index => index.version > COMPACT_INDEX_VERSION || index.ledger !== input.ledger)
    || raw.some(index => index.version > RAW_DAY_INDEX_VERSION || index.ledger !== input.ledger)
    || new Set(raw.map(index => index.date)).size !== raw.length
    || new Set(compact.map(index => index.period)).size !== compact.length) {
    throw new LedgerHistoryReadError("History indexes repeat, belong to another ledger or use an unsupported version");
  }
  for (const path of input.rawFiles ?? []) {
    const directories = input.days.map(day => `state/raw/${input.prefix.join("/")}/${DateStampSchema.parse(day).replaceAll("-", "/")}/`);
    if (!directories.some(directory => path.startsWith(directory) && !path.slice(directory.length).includes("/"))) {
      throw new LedgerHistoryReadError("Raw history file lies outside its named ledger day");
    }
  }
  for (const day of input.days) {
    DateStampSchema.parse(day);
    let covered = false;
    for (const period of ["yearly", "monthly", "daily"] as const) {
      const index = compact.find(index => index.period === period);
      if (period === "yearly" && index?.expired_through != null && day.slice(0, 4) <= index.expired_through) { covered = true; break; }
      const covers = period === "yearly" ? day.slice(0, 4) : period === "monthly" ? day.slice(0, 7) : day;
      const entry = index?.entries.find(entry => entry.covers === covers);
      if (entry?.state === "packed") {
        paths.add(`${posix.dirname(posix.dirname(indexes[period]))}/${period}/${period === "yearly" ? `${covers}/${covers}` : covers.replaceAll("-", "/")}.parquet`);
        covered = true;
        break;
      }
      if (entry !== undefined) { covered = true; break; }
    }
    if (covered && !planner) continue;
    const directory = `state/raw/${input.prefix.join("/")}/${day.replaceAll("-", "/")}/`;
    for (const path of input.rawFiles ?? []) {
      if (path.startsWith(directory)) paths.add(path);
    }
    if (!planner) {
      paths.add(rawIndex(day));
      const index = raw.find(index => index.date === day);
      if (index === undefined) continue;
      if (index.ledger !== input.ledger
        || createHash("sha256").update(index.files.join("\n")).digest("hex") !== index.content_sha256) {
        throw new LedgerHistoryReadError("Raw history filename digest differs");
      }
      for (const name of index.files) paths.add(`${posix.dirname(rawIndex(day))}/${name}`);
    }
  }
  paths.forEach(path => RelativePathSchema.parse(path));
  return [...paths];
}
