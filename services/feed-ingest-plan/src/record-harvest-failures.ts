/** Turn terminal article decisions into registered rejection ledger writes. */
import {
  HarvestArticleFailureReasonSchema, RejectedArticleRowContract, RejectedArticleRowSchema,
} from "@idhazh/common-contracts";
import type { CandidateRejectionRecord, RejectedArticleRow } from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import type { PlanInputs } from "./load-plan-inputs";
import type { RunContext } from "./resolve-run-context";

function normalizeHarvestFailures(rejections: readonly CandidateRejectionRecord[], context: RunContext) {
  const rows: RejectedArticleRow[] = [];
  for (const rejection of rejections) {
    if (rejection.subject !== "article" || rejection.stage !== "harvest-feeds"
      || !HarvestArticleFailureReasonSchema.safeParse(rejection.drop_reason).success) continue;
    if (rejection.candidate_id === null || rejection.url_key === null) {
      throw new Error("Terminal article failure lacks its captured candidate or article address");
    }
    const details = rejection.details;
    rows.push(RejectedArticleRowSchema.parse({
      run_id: context.run_id, attempt: context.writer.attempt, date: context.date,
      candidate_id: rejection.candidate_id, url_key: rejection.url_key, feed_id: rejection.feed_id,
      stage: rejection.stage, reason_code: rejection.drop_reason, freshness_cutoff_at: null,
      http_status: details.http_status, fetch_failure: details.fetch_failure,
      error_code: details.error_code,
      pacing_time_ms: details.pacing_time_ms, pacing_settings: details.pacing_settings,
    }));
  }
  return rows;
}

export async function recordHarvestFailures(
  rejections: readonly CandidateRejectionRecord[], context: RunContext, inputs: PlanInputs,
) {
  const rows = new Map(normalizeHarvestFailures(rejections, context).map(row => [row.candidate_id, row]));
  return writeRejectedArticles([...rows.values()], context, inputs);
}

export function sealCombinedRejections(
  harvest: readonly CandidateRejectionRecord[], selection: readonly RejectedArticleRow[],
  context: RunContext, inputs: PlanInputs,
) {
  const rows = [...normalizeHarvestFailures(harvest, context), ...selection];
  if (rows.some(row => row.run_id !== context.run_id || row.attempt !== context.writer.attempt || row.date !== context.date)) {
    throw new Error("Final rejection rows must belong to this run attempt and accounting day");
  }
  // The writer validates and settles duplicates by run, attempt and candidate before writing.
  rows.sort((a, b) => a.candidate_id.localeCompare(b.candidate_id));
  return writeRejectedArticles(rows, context, inputs);
}

export async function writeRejectedArticles(
  rows: readonly RejectedArticleRow[], context: Pick<RunContext, "writer" | "date">, inputs: PlanInputs,
) {
  const result = await persistLedger({
    ledger: "rejected-articles", rowContract: RejectedArticleRowContract, rows,
    registryEntry: inputs.registrations.rejected_articles, outputRoot: inputs.outputRoot,
    writerContext: context.writer, ledgerSettings: inputs.ledgerSettings, period: { tier: "raw", covers: context.date },
  });
  if (result.status === "skipped") throw new Error("Rejected metadata write was refused");
  return result;
}
