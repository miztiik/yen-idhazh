/** Which native health rows record this run before downstream work can fail? */
import type { FeedOutcomePayload, WriterIdentity } from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import type { LedgerRegistration, LedgerSettings } from "@idhazh/ledger-file-writer";
import { FeedHealthContract } from "@idhazh/common-contracts";
import type { FeedHistory } from "./read-feed-history";
import { retryableStatus } from "../harvest-feeds/robots-policy";
import type { HarvestResult } from "../harvest-feeds/harvest-types";
import type { FeedWriteReceipt } from "./own-feed-receipts";

export async function recordFeedHealth(input: {
  outcomes: readonly FeedOutcomePayload[]; articles: HarvestResult["articles"]; history: FeedHistory; now: string;
  writer: WriterIdentity; outputRoot: string; settings: LedgerSettings;
  health: LedgerRegistration;
  on_persisted?: (receipt: FeedWriteReceipt) => void;
}) {
  const rows = input.outcomes.map(outcome => {
    const history = input.history.sources.get(outcome.source.source_id);
    if (history === undefined) throw new Error("Feed outcome has no source history decision");
    const diagnostics = outcome.diagnostics;
    const failure = diagnostics?.fetch_failure;
    const skipped = outcome.fetch_status === "not_requested";
    const robots = failure === "robots-denied" || failure === "robots-unknown";
    const status = diagnostics?.http_status ?? null;
    const result = skipped ? "skipped" : robots ? "robots_denied"
      : failure === "unsafe-target" ? "blocked"
      : failure === "http" && status !== null ? retryableStatus.has(status) ? "transient" : "permanent"
      : outcome.fetch_status === "success" ? "ok" : "transient";
    return FeedHealthContract.schema.parse({
      version: FeedHealthContract.schemaVersion, run_id: input.writer.run_id, date: input.now.slice(0, 10),
      feed_id: outcome.source.source_id, publisher_id: outcome.source.publisher_id,
      checked_at: input.now, outcome: result,
      status, items: new Set(input.articles.flatMap(article => {
        const offered = article.candidate ?? article.rejection;
        return offered?.source_id === outcome.source.source_id && offered.canonical_url !== null
          ? [offered.canonical_url] : [];
      })).size,
      detail: skipped ? outcome.source.status !== "active" ? "source inactive"
        : "resting after repeated failures"
        : outcome.rejection_reason,
      endpoint_key: history.endpoint_key,
      robots_outcome: diagnostics?.robots === "unknown" ? "unreachable" : diagnostics?.robots ?? null,
      robots_checked_at: null, robots_status: diagnostics?.robots_http_status ?? null,
      target_attempted: !skipped && !robots && failure !== "unsafe-target",
    });
  });
  const health = await persistLedger({
    ledger: "feed-health", registryEntry: input.health, rowContract: FeedHealthContract, rows,
    period: { tier: "raw", covers: input.now.slice(0, 10) },
    writerContext: input.writer, outputRoot: input.outputRoot, ledgerSettings: input.settings,
  });
  if (health.status === "skipped") throw new Error("Required feed-health write was skipped");
  if (health.files.length > 0) input.on_persisted?.({
    ledger: "feed-health", day: input.now.slice(0, 10), files: health.files,
  });
  return { health, rows };
}
