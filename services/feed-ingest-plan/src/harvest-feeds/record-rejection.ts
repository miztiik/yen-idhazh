/** Validate one harvest rejection and persist the run's rows through the shared writer. */
import {
  CandidateRejectionRecordSchema, RejectionDetailsSchema, CONTRACT_VERSION,
} from "@idhazh/common-contracts";
import type { CandidateRejectionRecord, DropReason, RejectionDetails, SourceSnapshot } from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import type { HarvestContext, RejectionDestination } from "./harvest-types";
import { utcTimestamp } from "./harvest-types";
import type { FetchResult } from "./robots-policy";

export function fetchRejection(result: FetchResult, timeout_ms: number): {
  reason: DropReason; details: Partial<RejectionDetails>;
} {
  if (result.failure === "timeout") return { reason: "FETCH_TIMEOUT", details: { timeout_ms } };
  if (result.failure === "http") {
    if (result.http_status === null) throw new Error("HTTP rejection requires an observed status");
    return { reason: "FETCH_FAILED_HTTP", details: { http_status: result.http_status } };
  }
  return { reason: "FETCH_FAILED", details: {} };
}

export function recordRejection(
  source: Pick<SourceSnapshot, "source_id" | "feed_url">, context: HarvestContext, reason: DropReason,
  details: Partial<RejectionDetails> = {},
  article: {
    candidate_id: string; canonical_url: string | null; url_key: string | null;
    title: string | null; categories: string[];
  } | null = null,
): CandidateRejectionRecord {
  const rejected_at = utcTimestamp(context.clock);
  const row = CandidateRejectionRecordSchema.parse({
    date: rejected_at.slice(0, 10), correlation_id: context.correlation_id,
    source_id: source.source_id, feed_url: source.feed_url,
    subject: article === null ? "feed" : "article",
    candidate_id: article?.candidate_id ?? null,
    canonical_url: article?.canonical_url ?? null, url_key: article?.url_key ?? null,
    title: article?.title ?? null, categories: article?.categories ?? [],
    stage: "harvest-feeds", drop_reason: reason, details: RejectionDetailsSchema.parse(details), rejected_at,
  });
  (context.log ?? (record => console.error(JSON.stringify(record))))(row);
  return row;
}

export async function persistHarvestRejections(
  rows: readonly CandidateRejectionRecord[], context: HarvestContext, destination: RejectionDestination,
) {
  if (destination.ledgerSettings.format !== "parquet") throw new Error("harvest rejections require Parquet");
  const result = await persistLedger({
    ledger: "rejections",
    rowContract: { schema: CandidateRejectionRecordSchema, schemaVersion: CONTRACT_VERSION },
    rows, ...destination, writerContext: context.writer,
    period: { tier: "raw", covers: context.writer.run_id.slice(0, 10) },
  });
  if (rows.length && result.status === "skipped") {
    throw new Error(`harvest rejection persistence refused: rejections registry is ${result.warning.lifecycle_status}`);
  }
  return result;
}
