/** Which existing native files supply article responses and earlier paused-feed checks to one report? */
import { join } from "node:path";
import { RejectedArticleRowSchema } from "@idhazh/common-contracts";
import { PlanResponseSchema } from "../src/api/plan-response.schema";
import { FeedHealthStateUpdateResponseSchema } from "../src/api/feed-health-state.schema";
import type { ReportFailureEvidence } from "../src/reporting/failure-evidence-markdown";
import { loadPlanInputs } from "../src/load-plan-inputs";
import { readPlanningHistory } from "../src/read-ledger-history/read-run-history";
import { verifyParquetFiles } from "./feed-ingest-plan-verification";

export async function readReportFailureEvidence(input: {
  directory: string; root?: string; response: unknown; health?: unknown;
}): Promise<ReportFailureEvidence> {
  const response = PlanResponseSchema.parse(input.response);
  const health = input.health === undefined ? undefined : FeedHealthStateUpdateResponseSchema.parse(input.health);
  const gaps: [string, string, string][] = [];
  let articles: ReportFailureEvidence["articles"];
  const receipt = response.files.rejected_articles;
  if (receipt !== undefined) {
    try {
      const verified = await verifyParquetFiles(join(input.directory, "state"), "rejected-articles", receipt, {
        name: "rejected-articles", family: "feed-ingest-plan", lifecycle_status: "active",
        grain: "raw-and-compact", prefix: ["feed-ingest-plan", "rejected-articles"],
      });
      articles = RejectedArticleRowSchema.array().parse(verified.rows);
      if (articles.some(article => article.run_id !== response.run_id || article.attempt !== response.attempt)) {
        throw new Error("Report rejection file belongs to another execution");
      }
    } catch (error) {
      if (!(error instanceof Error && "code" in error && error.code === "ENOENT")) throw error;
      gaps.push(["Run", "Terminal article evidence file missing", "Aggregate failures retained; exact article responses unavailable"]);
    }
  }
  let earlier_checks: ReportFailureEvidence["earlier_checks"];
  if (input.root !== undefined && health?.availability?.feeds.some(feed =>
    feed.availability === "resting" || feed.availability === "retired")) {
    const inputs = await loadPlanInputs(input.root);
    // The result records the history bounds used by collection, not report-time defaults.
    inputs.harvest.config.feedback = {
      ...inputs.harvest.config.feedback, lifecycle_window_days: response.lifecycle_window_days,
      request_report_closed_days: response.request_report_closed_days,
    };
    inputs.clock_config.collect.reliability_window_days = response.reliability_window_days;
    const history = await readPlanningHistory(inputs, response.started_at);
    earlier_checks = history.uses.feed_rest.rows;
    if (history.input_gap || history.uses.feed_rest.gaps.length) gaps.push([
      "Historical evidence", "Earlier feed-check evidence incomplete",
      "Only validated saved checks can explain paused coverage; missing causes remain unavailable",
    ]);
  }
  return {
    ...(articles === undefined ? {} : { articles }),
    ...(earlier_checks === undefined ? {} : { earlier_checks }), gaps,
  };
}
