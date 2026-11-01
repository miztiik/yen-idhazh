/** Which regular local files belong to one registered planner UTC day or compact period? */
import { lstat, readdir, realpath } from "node:fs/promises";
import { resolve } from "node:path";
import { z } from "zod";
import {
  DateStampSchema, MonthStampSchema, PlannerLedgerNameSchema, RelPathSchema, YearStampSchema,
} from "@idhazh/common-contracts";
import type { LedgerRegistration } from "./ledger-types";
import { validateRegistration } from "./registration";
import { PlannerLedgerFileError } from "./read-planner-file";

function plannerPrefix(registration: LedgerRegistration) {
  const ledger = PlannerLedgerNameSchema.parse(registration.name);
  validateRegistration(ledger, registration);
  if (registration.family !== "feed-ingest-plan"
    || registration.prefix.join("/") !== `feed-ingest-plan/${ledger}`) {
    throw new PlannerLedgerFileError("Planner history requires its registered root");
  }
  return registration.prefix.join("/");
}

function calendarDay(day: string) {
  DateStampSchema.parse(day);
  if (new Date(`${day}T00:00:00Z`).toISOString().slice(0, 10) !== day) {
    throw new PlannerLedgerFileError("Invalid planner UTC day");
  }
  return day;
}

export function rawDayDirectory(registration: LedgerRegistration, day: string) {
  return `state/raw/${plannerPrefix(registration)}/${calendarDay(day).replaceAll("-", "/")}`;
}

export function compactPeriodFile(
  registration: LedgerRegistration, period: "daily" | "monthly" | "yearly", covers: string,
) {
  const prefix = plannerPrefix(registration);
  const stamp = period === "yearly" ? YearStampSchema : period === "monthly" ? MonthStampSchema : DateStampSchema;
  stamp.parse(covers);
  if (period === "daily") calendarDay(covers);
  if (period === "monthly" && (Number(covers.slice(5)) < 1 || Number(covers.slice(5)) > 12)) {
    throw new PlannerLedgerFileError("Invalid planner UTC month");
  }
  const file = period === "yearly" ? `${covers}/${covers}.parquet` : `${covers.replaceAll("-", "/")}.parquet`;
  return `state/compact/${prefix}/${period}/${file}`;
}

export async function regularPlannerPath(root: string, path: string, kind: "file" | "directory" = "file") {
  const segments = RelPathSchema.parse(path).split("/");
  let current = await realpath(root);
  for (const [index, segment] of segments.entries()) {
    current = resolve(current, segment);
    const info = await lstat(current);
    const directory = index < segments.length - 1 || kind === "directory";
    if (info.isSymbolicLink() || (directory ? !info.isDirectory() : !info.isFile())) {
      throw new PlannerLedgerFileError("Planner history path is not regular beneath its trusted root");
    }
  }
  return current;
}

function isMissing(error: unknown) {
  return error instanceof Error && "code" in error && error.code === "ENOENT";
}

export type PlannerRawDayFiles = {
  present: boolean;
  members: string[];
  refused: { path: string; reason: "nonregular-member" | "unsupported-member" }[];
};

export async function readPlannerDayFiles(
  root: string, registration: LedgerRegistration, day: string,
): Promise<PlannerRawDayFiles> {
  const path = rawDayDirectory(registration, day);
  let directory: string;
  try { directory = await regularPlannerPath(root, path, "directory"); }
  catch (error) {
    if (isMissing(error)) return { present: false, members: [], refused: [] };
    throw error;
  }
  const members: string[] = [];
  const refused: PlannerRawDayFiles["refused"] = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const member = `${path}/${entry.name}`;
    if (!entry.isFile()) {
      refused.push({ path, reason: "nonregular-member" });
    } else if (entry.name === "index.json") {
      continue;
    } else if (!entry.name.endsWith(".parquet")
      || entry.name !== entry.name.toLowerCase()
      || !z.uuid({ version: "v8" }).safeParse(entry.name.slice(0, -".parquet".length)).success) {
      refused.push({ path, reason: "unsupported-member" });
    } else members.push(member);
  }
  return { present: true, members: members.sort(), refused };
}

export async function readPlannerCompactFile(
  root: string, registration: LedgerRegistration, period: "daily" | "monthly" | "yearly", covers: string,
) {
  const path = compactPeriodFile(registration, period, covers);
  try { await regularPlannerPath(root, path); return path; }
  catch (error) {
    if (isMissing(error)) return undefined;
    throw error;
  }
}
