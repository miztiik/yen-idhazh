/** Validates, groups, renders, and writes new raw ledger rows. */
import { DateStampSchema } from "@idhazh/common-contracts";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";
import type { PersistLedgerInput, PersistLedgerResult } from "./ledger-types";
import { writeAtomically } from "./atomic-file";
import { buildRawPath, checkTrustedParent, toRelativePath } from "./ledger-paths";
import { validateLedgerInput, isMaintenanceJob } from "./registration";
import { buildStoredRawRow } from "./row-identity";
import { renderLedgerFile } from "./render-ledger-file";
import { createUnitId } from "./uuid/unit-id";
import type { PersistedLedgerFile } from "./ledger-types";

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export async function persistRawLedger<T extends object>(
  input: Extract<PersistLedgerInput<T>, { period: { tier: "raw" } }>,
): Promise<PersistLedgerResult> {
  const context = validateLedgerInput(input);
  if (input.rows.length === 0) return { status: "empty", files: [] };
  const registration = input.registryEntry;
  if (registration.lifecycle_status !== "active" && !isMaintenanceJob(context.writerContext.job)) {
    const warning = {
      event: "ledger_write_skipped" as const,
      ledger: context.ledger,
      family: registration.family,
      lifecycle_status: registration.lifecycle_status,
      row_count: input.rows.length,
    };
    process.stderr.write(`${JSON.stringify(warning)}\n`);
    return { status: "skipped", reason: "ledger_not_active", files: [], warning };
  }

  const validated = input.rows.map((candidate) => {
    const row = input.rowContract.schema.parse(candidate);
    if (!isObject(row)) throw new TypeError("ledger row contract did not produce an object");
    return row;
  });
  const groups = new Map<string, Record<string, unknown>[]>();
  for (const row of validated) {
    const day = input.partition_date ?? (Object.hasOwn(row, "date") ? row.date : input.period.covers);
    const covers = DateStampSchema.parse(day);
    const unit = context.writerContext;
    const generatedUnitId = createUnitId({
      ledger: context.ledger,
      covers,
      runId: unit.run_id,
      job: unit.job,
      pipelineName: unit.pipeline_name,
      taskName: unit.task_name,
      shard: unit.shard,
      producer: unit.producer,
    });
    const stored = buildStoredRawRow(row, context.ledger, covers, context.writerContext, generatedUnitId);
    groups.set(covers, [...(groups.get(covers) ?? []), stored]);
  }

  const rendered: { file: PersistedLedgerFile; data: Uint8Array; target: string }[] = [];
  for (const [covers, rows] of [...groups.entries()].sort(([left], [right]) => left.localeCompare(right))) {
    const result = await renderLedgerFile(rows, context.columns, context, covers, "raw");
    const filePath = buildRawPath(context.outputRoot, registration.prefix, covers, result.file.file_id);
    const relativePath = toRelativePath(context.outputRoot, filePath);
    rendered.push({
      file: { ...result.file, path: relativePath },
      data: result.data,
      target: resolve(context.outputRoot, ...relativePath.split("/")),
    });
  }
  await mkdir(context.outputRoot, { recursive: true });
  await Promise.all(rendered.map(({ target }) => checkTrustedParent(context.outputRoot, target)));
  for (const { target, data } of rendered) await writeAtomically(target, data);
  return { status: "written", files: rendered.map(({ file }) => file) };
}
