/** Finalize one immutable selection into an artifact and an allowlisted committed projection. */
import { randomUUID, createHash } from "node:crypto";
import { mkdir, rename, rm, writeFile } from "node:fs/promises";
import { join, relative, resolve } from "node:path";
import {
  PartitionedFeedBatchSchema, StageReferenceRequestSchema, SelectedArticleRowContract,
  SelectedArticlesArtifactSchema, selectedArticleMetadata,
} from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import type { PersistLedgerResult } from "@idhazh/ledger-file-writer";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import { requireStageConfiguration } from "./selection-operation";
import { stageStore } from "./stage-store";
import { RelativePathSchema } from "../config/service-settings";
import { PlanError } from "./plan-request";
import { appendDocumentTiming, currentDocumentState } from "./document-state";
import { recordStandaloneRun } from "./record-standalone-run";
import { healthFingerprint } from "./feed-health-state-operation";

type Result = {
  files: PersistLedgerResult; artifact: string; selected_count: number;
  run_files?: PersistLedgerResult; run_status?: "completed" | "partial" | "failed";
};
const finalized = new WeakMap<PlanInputs, Map<string, { fingerprint: string; result: Promise<Result> }>>();
export async function executePersistence(raw: unknown, inputs: PlanInputs, runtime: PlanRuntime): Promise<Result> {
  const request = StageReferenceRequestSchema.parse(raw);
  const batch = stageStore(inputs).read("partitioned", request.batch_id, PartitionedFeedBatchSchema);
  requireStageConfiguration(batch, inputs, runtime);
  const state = currentDocumentState(inputs, batch.context.run_id);
  if (state !== undefined) {
    const document = await state;
    if (document.health_written && document.health_fingerprint !== healthFingerprint(batch.health_rows)) {
      throw new PlanError("REQUEST_CONFLICT", "Selection differs from this execution's finalized health capture", "batch_id");
    }
  }
  const artifact = SelectedArticlesArtifactSchema.parse({
    schema_version: SelectedArticleRowContract.schemaVersion, run_id: batch.context.run_id,
    attempt: batch.context.writer.attempt, date: batch.context.date, evaluated_at: batch.evaluated_at,
    articles: batch.articles.map(article => ({ ...selectedArticleMetadata(article), article_text: article.article_text })),
  });
  const bytes = JSON.stringify(artifact);
  const fingerprint = createHash("sha256").update(JSON.stringify({
    artifact, strategy: batch.strategy, dispatch_count: batch.dispatch_count,
  })).digest("hex");
  const key = `${batch.context.run_id}:${batch.context.writer.attempt}`;
  let completed = finalized.get(inputs);
  if (completed === undefined) { completed = new Map(); finalized.set(inputs, completed); }
  const previous = completed.get(key);
  if (previous !== undefined) {
    if (previous.fingerprint !== fingerprint) throw new PlanError("REQUEST_CONFLICT", "This execution already finalized a different selection or partition", "batch_id");
    return previous.result;
  }
  const result = (async (): Promise<Result> => {
    const began = performance.now();
    const metadata = batch.articles.map(article => ({
      ...selectedArticleMetadata(article), run_id: batch.context.run_id, attempt: batch.context.writer.attempt, date: batch.context.date,
    }));
    const directory = resolve(inputs.root, inputs.settings.inputs.artifact_root, batch.context.run_id, String(batch.context.writer.attempt));
    const target = join(directory, "selected-articles.json");
    const temporary = `${target}.${randomUUID()}.tmp`;
    await mkdir(directory, { recursive: true });
    try {
      await writeFile(temporary, bytes, { flag: "wx" });
      await rename(temporary, target);
    } finally { await rm(temporary, { force: true }); }
    const files = await persistLedger({
      ledger: "selected-articles", rowContract: SelectedArticleRowContract, rows: metadata,
      registryEntry: inputs.registrations.selected_articles, outputRoot: inputs.outputRoot,
      writerContext: batch.context.writer, ledgerSettings: inputs.ledgerSettings, period: { tier: "raw", covers: batch.context.date },
    });
    if (files.status === "skipped") throw new Error("Selected metadata write was refused");
    const path = RelativePathSchema.parse(relative(inputs.root, target).replaceAll("\\", "/"));
    await appendDocumentTiming(inputs, batch.context.run_id, { operation: "persist", duration_ms: Math.round(performance.now() - began), status: "completed" });
    const run = await recordStandaloneRun(inputs, batch, path);
    return { files, artifact: path, selected_count: metadata.length, ...(run === undefined ? {} : { run_files: run.files, run_status: run.row.status }) };
  })();
  while (completed.size >= inputs.settings.listener.max_stage_batches) completed.delete(completed.keys().next().value!);
  completed.set(key, { fingerprint, result });
  try { return await result; }
  catch (error) { completed.delete(key); throw error; }
}
