/** Validates, renders, and writes one compact ledger period while retaining row identities. */
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";
import type { PersistLedgerInput, PersistLedgerResult } from "./ledger-types";
import { writeAtomically } from "./atomic-file";
import { buildCompactPath, checkTrustedParent, toRelativePath } from "./ledger-paths";
import { validateLedgerInput } from "./registration";
import { buildStoredCompactRow } from "./row-identity";
import { renderLedgerFile } from "./render-ledger-file";

export async function persistCompactLedger<T extends object>(
  input: Extract<PersistLedgerInput<T>, { period: { tier: "compact" } }>,
): Promise<PersistLedgerResult> {
  const context = validateLedgerInput(input);
  const compactPeriod = input.period;
  const compactRows = input.rows.map((candidate) =>
    buildStoredCompactRow(
      candidate,
      input.rowContract.schema,
      context.ledger,
      compactPeriod,
    ),
  );
  const result = await renderLedgerFile(
    compactRows,
    context.columns,
    context,
    compactPeriod.covers,
    "compact",
  );
  const filePath = buildCompactPath(context.outputRoot, input.registryEntry.prefix, compactPeriod);
  const relativePath = toRelativePath(context.outputRoot, filePath);
  const target = resolve(context.outputRoot, ...relativePath.split("/"));
  await mkdir(context.outputRoot, { recursive: true });
  await checkTrustedParent(context.outputRoot, target);
  await writeAtomically(target, result.data);
  return { status: "written", files: [{ ...result.file, path: relativePath }] };
}
