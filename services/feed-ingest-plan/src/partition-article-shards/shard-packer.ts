/** Which configured allocation becomes a validated dispatch without changing editorial choices? */
import { FeedIngestDispatchSchema } from "@idhazh/common-contracts";
import type { FeedIngestCandidate, EditorialSelectionRow, WriterIdentity } from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import type { LedgerRegistration, LedgerSettings } from "@idhazh/ledger-file-writer";
import type { z } from "zod";
import type { FeedPartitionConfigSchema } from "@idhazh/common-contracts";
import { preparePartitionInput, resolvePartitionRequest } from "./partition-input";
import type { PartitionRequest } from "./partition-input";
import { assignBinPack } from "./bin-pack";
import { assignRoundRobin } from "./round-robin";
import { DispatchContract } from "../metrics/audit-contracts";

export function partitionArticles(input: Readonly<{
  selections: readonly EditorialSelectionRow[];
  candidates: readonly FeedIngestCandidate[];
  context: Readonly<{ date: string; run_id: string; correlation_id: string }>;
  settings: z.input<typeof FeedPartitionConfigSchema>;
  request?: PartitionRequest;
}>) {
  const partition = resolvePartitionRequest(input.settings, input.request);
  const articles = preparePartitionInput(input.selections, input.candidates, input.context);
  const assignments = partition.strategy === "bin-pack"
    ? assignBinPack(articles, partition.dispatch_count)
    : assignRoundRobin(articles, partition.dispatch_count);
  const work = Array<number>(partition.dispatch_count).fill(0);
  const dispatches = articles.map(article => {
    const worker = assignments.get(article.selection.candidate_id);
    if (worker === undefined) throw new Error("Selected article has no worker assignment");
    work[worker] = work[worker]! + article.selection.estimated_work;
    if (!Number.isFinite(work[worker])) throw new Error("Estimated worker work exceeds the numeric range");
    return FeedIngestDispatchSchema.parse({
      ...article, partition: { ...partition, worker_assignment: worker },
    });
  });
  return { ...partition, dispatches, work };
}

export async function persistDispatches(
  result: ReturnType<typeof partitionArticles>,
  context: Readonly<{
    outputRoot: string; writerContext: WriterIdentity; ledgerSettings: LedgerSettings;
    registration: LedgerRegistration; date: string; correlation_id: string;
  }>,
) {
  if (context.registration.name !== "article-dispatches" || context.ledgerSettings.format !== "parquet") {
    throw new Error("Dispatch persistence requires its registered Parquet ledger");
  }
  if (context.writerContext.run_id.slice(0, 10) !== context.date
    || result.dispatches.some(row => row.selection.date !== context.date
      || row.selection.correlation_id !== context.correlation_id)) {
    throw new Error("Dispatch writer differs from the selection planning context");
  }
  const stored = await persistLedger({
    ledger: "article-dispatches", registryEntry: context.registration, outputRoot: context.outputRoot,
    writerContext: context.writerContext, ledgerSettings: context.ledgerSettings,
    period: { tier: "raw", covers: context.date },
    rowContract: DispatchContract,
    rows: result.dispatches,
  });
  if (stored.status === "skipped") throw new Error("Dispatch ledger is unavailable");
  return stored;
}
