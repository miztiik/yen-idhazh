/** Read one named planner UTC day, merging raw and compact representations of its facts. */
import { realpath } from "node:fs/promises";
import { resolve, relative } from "node:path";
import { DateStampSchema, PlannerLedgerNameSchema } from "@idhazh/common-contracts";
import type { PlannerStoredFileEnvelope } from "@idhazh/common-contracts";
import { readStoredPlannerParquet } from "@idhazh/ledger-file-writer";
import type { LedgerRegistration, LedgerRowContract } from "@idhazh/ledger-file-writer";
import type { LedgerDayInput } from "../config/service-settings";
import { readPlannerParquet } from "./read-planner-parquet";
import { LedgerHistoryReadError } from "./ledger-history-error";
import { classifyPlannerHistoryGap } from "./planner-history-gap";
import {
  compactPeriodFile, fixedHistoryRevision, listExactRawDayMembers, rawDayDirectory,
  readNamedGitMember, verifiedHistoryRevision, verifyRawDayMember,
} from "./raw-day-members";
type PlannerHistoryFile<T extends object> = {
  envelope: PlannerStoredFileEnvelope; rows: T[]; bytes: number; file_sha256: string;
};
export type PlannerHistoryCache<T extends object> = {
  files: Map<string, Promise<PlannerHistoryFile<T>>>;
  revision?: Promise<string>;
  trees: Map<string, Promise<string>>;
};
export function createPlannerHistoryCache<T extends object>(): PlannerHistoryCache<T> {
  return { files: new Map(), trees: new Map() };
}
export async function readPlannerDay<T extends object>(
  root: string, registration: LedgerRegistration, day: LedgerDayInput, contract: LedgerRowContract<T>,
  cache: PlannerHistoryCache<T> = createPlannerHistoryCache<T>(),
) {
  return readPlannerDayUsing(root, registration, day, cache, "strict",
    (path, ledger) => readPlannerParquet(path, ledger, contract),
    row => "date" in row && row.date === day.day);
}

export async function readStoredPlannerDay(
  root: string, registration: LedgerRegistration, day: LedgerDayInput,
  cache: PlannerHistoryCache<Record<string, unknown>> = createPlannerHistoryCache(),
) {
  return readPlannerDayUsing(root, registration, day, cache, "stored", readStoredPlannerParquet,
    (row, envelope) => envelope.tier === "raw"
      || row.date === day.day || !DateStampSchema.safeParse(row.date).success);
}

async function readPlannerDayUsing<T extends object>(
  root: string, registration: LedgerRegistration, day: LedgerDayInput, cache: PlannerHistoryCache<T>,
  mode: "stored" | "strict",
  readFile: (path: string, ledger: PlannerStoredFileEnvelope["ledger"]) => Promise<PlannerHistoryFile<T>>,
  includesRow: (row: T, envelope: PlannerStoredFileEnvelope) => boolean,
) {
  if (day.raw_index !== undefined) throw new LedgerHistoryReadError("Planner raw days do not accept raw_index");
  if (day.indexes !== undefined) throw new LedgerHistoryReadError("Planner compact indexes are no longer accepted");
  rawDayDirectory(registration, day.day);
  const ledger = PlannerLedgerNameSchema.parse(registration.name);
  const files: PlannerHistoryFile<T>[] = [];
  let represented: boolean | null = null;
  let covered = false;
  let complete = true;
  const gaps = new Map<string, string>();
  function readParquet(path: string) {
    const key = `${mode}:${path}`;
    let pending = cache.files.get(key);
    if (pending === undefined) { pending = readFile(path, ledger); cache.files.set(key, pending); }
    return pending;
  }
  async function attempt<R>(path: string, read: () => Promise<R>): Promise<R | undefined> {
    try { return await read(); }
    catch (error) {
      const code = classifyPlannerHistoryGap(error);
      if (code === null) throw error;
      complete = false;
      if (!gaps.has(code)) gaps.set(code, relative(root, path).replaceAll("\\", "/"));
      return undefined;
    }
  }
  let revision: string | undefined;
  if (day.raw_files === undefined || day.raw_revision !== undefined) {
    revision = await attempt(root, async () => {
      const requested = day.raw_revision === undefined
        ? await (cache.revision ??= fixedHistoryRevision(root))
        : await verifiedHistoryRevision(root, day.raw_revision);
      const captured = await (cache.revision ??= Promise.resolve(requested));
      if (requested !== captured) {
        throw new LedgerHistoryReadError("Raw and compact history revisions differ within one capture");
      }
      return captured;
    });
  }
  const capturedRevision = revision;
  if (capturedRevision !== undefined) for (const period of ["yearly", "monthly", "daily"] as const) {
    const covers = period === "yearly" ? day.day.slice(0, 4) : period === "monthly" ? day.day.slice(0, 7) : day.day;
    const path = compactPeriodFile(registration, period, covers);
    const before = complete;
    const member = await attempt(resolve(root, path), () =>
      readNamedGitMember(root, path, capturedRevision, cache.trees));
    if (member === undefined) {
      if (!complete || !before) break;
      continue;
    }
    const held = await attempt(resolve(root, path), async () => {
      const held = await readParquet(resolve(root, path));
      if (held.envelope.tier !== "compact" || held.envelope.period !== period
        || held.envelope.covers !== covers || held.bytes !== member.bytes.byteLength
        || held.file_sha256 !== member.file_sha256 || held.rows.length === 0) {
        throw new LedgerHistoryReadError("Planner compact file differs from its selected Git revision");
      }
      return held;
    });
    if (held !== undefined) {
      covered = true;
      represented = true;
      files.push(held);
    }
    break;
  }
  let rawPaths = day.raw_files?.map(path => resolve(root, path));
  const committedDigests = new Map<string, string>();
  if (rawPaths === undefined || day.raw_revision !== undefined) {
    const discovered = await attempt(resolve(root, `state/raw/${registration.prefix.join("/")}`), async () => {
      if (revision === undefined) throw new LedgerHistoryReadError("Raw history has no captured Git revision");
      const listing = await listExactRawDayMembers(root, registration, day.day, revision, cache.trees);
      const expected = listing.members.map(member => resolve(root, member.path));
      if (rawPaths !== undefined && [...rawPaths].sort().join("\n") !== [...expected].sort().join("\n")) {
        throw new LedgerHistoryReadError("Supplied raw members differ from the complete named Git day");
      }
      for (const member of listing.members) {
        committedDigests.set(resolve(root, member.path), (await verifyRawDayMember(root, member)).file_sha256);
      }
      return expected;
    });
    rawPaths = discovered;
  }
  if (rawPaths !== undefined) {
    covered = true;
    represented = rawPaths.length > 0 ? true : represented ?? (complete ? false : null);
    if (new Set(rawPaths).size !== rawPaths.length) throw new LedgerHistoryReadError("Planner raw input repeats a file");
    for (const path of rawPaths) {
      await attempt(path, async () => {
        const local = relative(root, path).replaceAll("\\", "/");
        const suffix = `raw/${registration.prefix.join("/")}/${day.day.replaceAll("-", "/")}/`;
        if (local.startsWith("../") || (local !== `${suffix}${local.split("/").at(-1)}`
          && local !== `state/${suffix}${local.split("/").at(-1)}`)) {
          throw new LedgerHistoryReadError("Planner raw file lies outside its registered UTC day");
        }
        const actual = await realpath(path);
        const expected = resolve(await realpath(root), local);
        if (actual !== expected) throw new LedgerHistoryReadError("Planner raw file crosses a linked directory");
        const held = await readParquet(path);
        const digest = committedDigests.get(path);
        if (digest !== undefined && held.file_sha256 !== digest) {
          throw new LedgerHistoryReadError("Raw history bytes changed during the named revision read");
        }
        if (held.envelope.tier !== "raw" || held.envelope.covers !== day.day) {
          throw new LedgerHistoryReadError("Planner raw file differs from its named day");
        }
        files.push(held);
      });
    }
  }
  for (const [code, path] of gaps) console.error(JSON.stringify({ event: "planner_history_gap", ledger, day: day.day, code, path }));
  return {
    day: day.day, represented, complete: covered && complete,
    rows: files.flatMap(file => file.rows.filter(row => includesRow(row, file.envelope))),
    gaps: [...gaps.keys()],
  };
}
