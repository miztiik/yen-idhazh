/** Retain terminal article download and extraction failures through the registered ledger writer. */
import {
  HarvestArticleFailureReasonSchema, RejectedArticleRowContract, RejectedArticleRowSchema,
} from "@idhazh/common-contracts";
import type { CandidateRejectionRecord } from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import type { PlanInputs } from "./load-plan-inputs";
import type { RunContext } from "./resolve-run-context";

export async function recordHarvestFailures(
  rejections: readonly CandidateRejectionRecord[], context: RunContext, inputs: PlanInputs,
) {
  const rows = new Map<string, ReturnType<typeof RejectedArticleRowSchema.parse>>();
  for (const rejection of rejections) {
    if (rejection.subject !== "article" || rejection.stage !== "harvest-feeds"
      || !HarvestArticleFailureReasonSchema.safeParse(rejection.drop_reason).success) continue;
    if (rejection.drop_reason === "MISSING_REQUIRED_FIELDS" && rejection.details.http_status === null) continue;
    if (rejection.candidate_id === null || rejection.url_key === null) {
      throw new Error("Terminal article failure lacks its offered identity");
    }
    const details = rejection.details;
    rows.set(rejection.candidate_id, RejectedArticleRowSchema.parse({
      run_id: context.run_id, attempt: context.writer.attempt, date: context.date,
      candidate_id: rejection.candidate_id, url_key: rejection.url_key, feed_id: rejection.feed_id,
      stage: rejection.stage, reason_code: rejection.drop_reason, freshness_cutoff_at: null,
      http_status: details.http_status, fetch_failure: details.fetch_failure,
      error_code: details.error_code, robots: details.robots,
      robots_http_status: details.robots_http_status, robots_failure: details.robots_failure,
    }));
  }
  const result = await persistLedger({
    ledger: "rejected-articles", rowContract: RejectedArticleRowContract, rows: [...rows.values()],
    registryEntry: inputs.registrations.rejected_articles, outputRoot: inputs.outputRoot,
    writerContext: context.writer, ledgerSettings: inputs.ledgerSettings, period: { tier: "raw", covers: context.date },
  });
  if (result.status === "skipped") throw new Error("Terminal article failure write was refused");
  return result;
}
