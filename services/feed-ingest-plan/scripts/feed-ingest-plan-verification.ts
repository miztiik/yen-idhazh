/** Verify actual planner files and artifact agreement without test-fixture dependencies. */
import { readFile, realpath } from "node:fs/promises";
import { isDeepStrictEqual } from "node:util";
import { isAbsolute, relative, resolve } from "node:path";
import { z } from "zod";
import {
  DateStampSchema, DiscoveredArticleRowContract, FeedHealthStateRowContract, PlanRunRowContract,
  SelectedArticleRowContract, SelectedArticlesArtifactSchema, selectedArticleMetadata,
} from "../../../packages/common-contracts/src/index";
import type { LedgerRegistration, LedgerRowContract, PersistLedgerResult } from "../../../packages/ledger-file-writer/src/index";
import { readPlannerParquet } from "../src/read-ledger-history/read-planner-parquet";
import { RelativePathSchema } from "../src/config/service-settings";
import { PlanResponseSchema } from "../src/api/plan-response.schema";

export const plannerContracts = {
  "discovered-articles": DiscoveredArticleRowContract, "selected-articles": SelectedArticleRowContract,
  "feed-health-state": FeedHealthStateRowContract, "plan-runs": PlanRunRowContract,
};
export type PlannerLedger = keyof typeof plannerContracts;
export function validateLedgerFilePath(path: string, fileId: string, covers: string, registration: LedgerRegistration) {
  DateStampSchema.parse(covers);
  const name = z.enum(["discovered-articles", "selected-articles", "feed-health-state", "plan-runs"]).parse(registration.name);
  if (registration.family !== "feed-ingest-plan" || registration.prefix.join("/") !== `feed-ingest-plan/${name}`
    || !/^[0-9a-f]{8}-[0-9a-f]{4}-8[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(fileId)
    || path !== `raw/feed-ingest-plan/${name}/${covers.replaceAll("-", "/")}/${fileId}.parquet`) {
    throw new Error("Planner output path differs from its registered current identity");
  }
  return path;
}
export async function verifyParquetFiles(
  root: string, ledger: PlannerLedger, written: PersistLedgerResult, registration: LedgerRegistration,
  expectedRows?: readonly object[],
) {
  if (registration.name !== ledger) throw new Error("Planner receipt names a different ledger");
  if (written.status === "skipped") throw new Error("Required planner write was skipped");
  if (written.status === "empty") {
    if (written.files.length || (expectedRows !== undefined && expectedRows.length)) throw new Error("Explicit empty write has no rows or files");
    return { row_count: 0, rows: [] as object[], files: [] as string[] };
  }
  const rows: object[] = [];
  const files: string[] = [];
  const localRoot = await realpath(root);
  for (const file of written.files) {
    const path = validateLedgerFilePath(file.path, file.file_id, file.covers, registration);
    if (files.includes(path) || file.unit_id !== undefined) throw new Error("Planner receipt repeats a file or injects generic unit identity");
    const actualPath = await realpath(resolve(localRoot, ...path.split("/")));
    const local = relative(localRoot, actualPath);
    if (isAbsolute(local) || local === ".." || local.startsWith(`..\\`) || local.startsWith("../")) throw new Error("Planner file escapes its output root");
    const contract: LedgerRowContract<object> = plannerContracts[ledger];
    const actual = await readPlannerParquet(actualPath, ledger, contract);
    if (actual.envelope.tier !== "raw" || actual.envelope.file_id !== file.file_id
      || actual.envelope.covers !== file.covers || actual.envelope.content_sha256 !== file.content_sha256
      || actual.rows.length !== file.row_count) throw new Error("Planner receipt differs from native file readback");
    rows.push(...actual.rows);
    files.push(path);
  }
  if (written.files.length === 0 || (expectedRows !== undefined && !isDeepStrictEqual(rows, expectedRows))) {
    throw new Error("Planner written rows differ from the declared result");
  }
  return { row_count: rows.length, rows, files };
}

export async function verifyPlanningCompletion(
  root: string, raw: unknown, registrations: {
    discovered_articles: LedgerRegistration; selected_articles: LedgerRegistration;
    feed_health_state: LedgerRegistration; plan_runs: LedgerRegistration;
  }, repositoryRoot = resolve(root, ".."),
) {
  const summary = PlanResponseSchema.parse(raw);
  const verified: Partial<Record<PlannerLedger, Awaited<ReturnType<typeof verifyParquetFiles>>>> = {};
  for (const [key, name] of [
    ["discovered_articles", "discovered-articles"], ["selected_articles", "selected-articles"],
    ["feed_health_state", "feed-health-state"], ["plan_runs", "plan-runs"],
  ] as const) {
    const files = summary.files[key];
    if (files !== undefined) verified[name] = await verifyParquetFiles(root, name, files, registrations[key]);
    else if (summary.planning_complete) throw new Error("Completed planner run lacks an explicit ledger result");
  }
  const run = verified["plan-runs"]?.rows.map(row => PlanRunRowContract.schema.parse(row));
  const expectedRun = PlanRunRowContract.schema.parse(Object.fromEntries(Object.keys(PlanRunRowContract.schema.shape)
    .map(key => [key, summary[key as keyof typeof summary]])));
  if (run?.length !== 1 || !isDeepStrictEqual(run[0], expectedRun)) {
    throw new Error("Planner response differs from its explicit native run outcome");
  }
  const selected = (verified["selected-articles"]?.rows ?? []).map(row => SelectedArticleRowContract.schema.parse(row));
  if (summary.planning_complete && selected.length !== summary.selected_count) throw new Error("Selected file does not match the completed run count");
  if (summary.selected_articles_artifact !== null) {
    const path = resolve(repositoryRoot, RelativePathSchema.parse(summary.selected_articles_artifact));
    const local = relative(await realpath(repositoryRoot), await realpath(path));
    if (isAbsolute(local) || local === ".." || local.startsWith(`..\\`) || local.startsWith("../")) throw new Error("Selected artifact escapes its repository");
    const artifact = SelectedArticlesArtifactSchema.parse(JSON.parse(await readFile(path, "utf8")));
    if (artifact.run_id !== summary.run_id || artifact.attempt !== summary.attempt || artifact.date !== summary.date
      || artifact.evaluated_at !== summary.evaluated_at || artifact.articles.length !== summary.selected_count) {
      throw new Error("Selected artifact header or count differs from its run");
    }
    const expected = artifact.articles.map(article => ({
      ...selectedArticleMetadata(article), run_id: artifact.run_id, attempt: artifact.attempt, date: artifact.date,
    }));
    if (selected.length && !isDeepStrictEqual(selected, expected)) throw new Error("Artifact and committed allowlisted projection differ");
    if (!isDeepStrictEqual(artifact.articles.map(article => article.url_key), summary.selected_url_keys)) {
      throw new Error("Artifact order differs from the selected response");
    }
    if (!isDeepStrictEqual(artifact.articles.map(({ url_key, editorial_rank, worker_assignment }) =>
      ({ url_key, editorial_rank, worker_assignment })), summary.assignments)) throw new Error("Artifact worker assignments differ from the selected response");
  } else if (summary.planning_complete) throw new Error("Completed planner run lacks its selected artifact");
  return verified;
}
