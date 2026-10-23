/** Which native health and retirement rows record this run before downstream work can fail? */
import type { FeedOutcomePayload, WriterIdentity } from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import type { LedgerRegistration, LedgerSettings } from "@idhazh/ledger-file-writer";
import { FeedHealthContract, FeedRetirementContract } from "@idhazh/common-contracts";
import type { FeedHistory } from "./read-feed-history";
import { retryableStatus } from "../harvest-feeds/robots-policy";
import type { HarvestResult } from "../harvest-feeds/harvest-types";

export async function recordFeedHealth(input: {
  outcomes: readonly FeedOutcomePayload[]; articles: HarvestResult["articles"]; history: FeedHistory; now: string;
  writer: WriterIdentity; outputRoot: string; settings: LedgerSettings;
  health: LedgerRegistration; retirements: LedgerRegistration;
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
      feed_id: outcome.source.source_id, checked_at: input.now, outcome: result,
      status, items: new Set(input.articles.flatMap(article => {
        const offered = article.candidate ?? article.rejection;
        return offered?.source_id === outcome.source.source_id && offered.canonical_url !== null
          ? [offered.canonical_url] : [];
      })).size,
      detail: skipped ? outcome.source.status !== "active" ? "source inactive"
        : history.lifecycle === "retired" ? history.retirement_cause === "http_410"
          ? "address retired after repeated 410 Gone" : "address retired after sustained low yield"
          : "resting after repeated failures"
        : outcome.rejection_reason,
      endpoint_key: history.endpoint_key,
      robots_outcome: diagnostics?.robots === "unknown" ? "unreachable" : diagnostics?.robots ?? null,
      robots_checked_at: null, robots_status: diagnostics?.robots_http_status ?? null,
      target_attempted: !skipped && !robots && failure !== "unsafe-target",
    });
  });
  const write = async <T extends object>(
    ledger: "feed-health" | "feed-retirements", registration: LedgerRegistration,
    contract: { schema: import("zod").z.ZodType<T>; schemaVersion: string }, rows: readonly T[],
  ) => {
    const result = await persistLedger({
      ledger, registryEntry: registration, rowContract: contract, rows,
      period: { tier: "raw", covers: input.now.slice(0, 10) },
      writerContext: input.writer, outputRoot: input.outputRoot, ledgerSettings: input.settings,
    });
    if (result.status === "skipped") throw new Error(`Required ${ledger} write was skipped`);
    return result;
  };
  const retirements = await write("feed-retirements", input.retirements, FeedRetirementContract, input.history.new_retirements);
  const health = await write("feed-health", input.health, FeedHealthContract, rows);
  return { health, retirements, rows };
}
