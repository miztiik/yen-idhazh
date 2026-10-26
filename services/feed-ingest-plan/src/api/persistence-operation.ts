/** Serialize one selected result into an artifact and an explicit body-free Parquet projection. */
import { randomUUID } from "node:crypto";
import { mkdir, rename, rm, writeFile } from "node:fs/promises";
import { join, relative, resolve } from "node:path";
import {
  PartitionedFeedBatchSchema, StageReferenceRequestSchema, SelectedArticleRowContract,
  SelectedArticlesArtifactSchema, selectedArticleMetadata,
} from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import { requireStageConfiguration } from "./selection-operation";
import { stageStore } from "./stage-store";
import { RelativePathSchema } from "../config/service-settings";

export async function executePersistence(raw: unknown, inputs: PlanInputs, runtime: PlanRuntime) {
  const request = StageReferenceRequestSchema.parse(raw);
  const batch = stageStore(inputs).read("partitioned", request.batch_id, PartitionedFeedBatchSchema);
  requireStageConfiguration(batch, inputs, runtime);
  const artifact = SelectedArticlesArtifactSchema.parse({
    schema_version: SelectedArticleRowContract.schemaVersion,
    run_id: batch.context.run_id, attempt: batch.context.writer.attempt,
    date: batch.context.date, evaluated_at: batch.evaluated_at,
    articles: batch.articles.map(article => ({ ...selectedArticleMetadata(article), article_text: article.article_text })),
  });
  const metadata = batch.articles.map(article => ({
    ...selectedArticleMetadata(article), run_id: batch.context.run_id, attempt: batch.context.writer.attempt, date: batch.context.date,
  }));
  const directory = resolve(inputs.root, inputs.settings.inputs.artifact_root, batch.context.run_id, String(batch.context.writer.attempt));
  const target = join(directory, `${batch.batch_id}.json`);
  const temporary = `${target}.${randomUUID()}.tmp`;
  await mkdir(directory, { recursive: true });
  try {
    await writeFile(temporary, JSON.stringify(artifact), { flag: "wx" });
    await rename(temporary, target);
  } finally { await rm(temporary, { force: true }); }
  const files = await persistLedger({
    ledger: "selected-articles", rowContract: SelectedArticleRowContract, rows: metadata,
    registryEntry: inputs.registrations.selected_articles, outputRoot: inputs.outputRoot,
    writerContext: batch.context.writer, ledgerSettings: inputs.ledgerSettings,
    period: { tier: "raw", covers: batch.context.date },
  });
  if (files.status === "skipped") throw new Error("Selected metadata write was refused");
  return {
    files,
    artifact: RelativePathSchema.parse(relative(inputs.root, target).replaceAll("\\", "/")),
    selected_count: metadata.length,
  };
}
