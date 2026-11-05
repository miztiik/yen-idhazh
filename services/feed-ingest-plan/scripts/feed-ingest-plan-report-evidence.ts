/** Which named native files supply terminal article details and earlier paused-feed checks to one report? */
import { join } from "node:path";
import { PlannerSavedResponseSchema, RejectedArticleRowSchema } from "@idhazh/common-contracts";
import type { ReportFailureEvidence } from "../src/reporting/failure-evidence-markdown";
import type { ReportDiagnosticIdentity } from "../src/reporting/article-failure-evidence";
import { loadPlanInputs } from "../src/load-plan-inputs";
import { readPlanningHistory } from "../src/read-ledger-history/read-run-history";
import { verifyParquetFiles } from "./feed-ingest-plan-verification";
import { readArticleFailureDiagnostics } from "./read-article-failure-diagnostics";
import { readServerEvidence } from "../../serve-pipeline-apis/src/read-server-evidence";
import type { ServerEvidence } from "../../serve-pipeline-apis/src/server-evidence";

export async function readReportFailureEvidence(input: {
  directory: string; root?: string; response?: unknown;
  execution?: ReportDiagnosticIdentity; servers?: readonly ServerEvidence[];
}): Promise<ReportFailureEvidence> {
  const saved = input.response === undefined ? undefined : PlannerSavedResponseSchema.parse(input.response);
  const captured = saved === undefined ? undefined : "planning_complete" in saved ? saved : saved.failure?.execution;
  const expected: { run_id?: string; attempt?: number; traceId?: string } = {};
  for (const field of ["run_id", "attempt", "traceId"] as const) {
    const explicit = input.execution?.[field];
    const recorded = captured?.[field];
    if (explicit !== undefined && recorded != null && explicit !== recorded) {
      throw new Error("Report inputs belong to another execution");
    }
  }
  const run_id = input.execution?.run_id ?? captured?.run_id;
  const attempt = input.execution?.attempt ?? captured?.attempt;
  const traceId = input.execution?.traceId ?? captured?.traceId;
  if (run_id != null) expected.run_id = run_id;
  if (attempt != null) expected.attempt = attempt;
  if (traceId != null) expected.traceId = traceId;
  const diagnostics = await readArticleFailureDiagnostics({
    directory: input.directory, expected, servers: input.servers ?? await readServerEvidence(input.directory),
  });
  if (saved === undefined || !("planning_complete" in saved)) return diagnostics;
  const response = saved;
  const health = response.health?.status === "summarized" ? response.health : null;
  const gaps = [...diagnostics.gaps];
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
    article_diagnostics: diagnostics.article_diagnostics,
    ...(articles === undefined ? {} : { articles }),
    ...(earlier_checks === undefined ? {} : { earlier_checks }), gaps,
  };
}
