/** Write one explicit run outcome with measured clocks and no copied article or audit payload. */
import { PlanRunRowContract, PlanRunRowSchema } from "@idhazh/common-contracts";
import type { PlanRunRow } from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import type { PlanInputs } from "./load-plan-inputs";
import type { RunContext } from "./resolve-run-context";

export async function recordPlanRun(inputs: PlanInputs, context: RunContext, values: {
  duration_ms: number | null; status: PlanRunRow["status"]; failure_code: string | null;
  selected_count: number; strategy: PlanRunRow["strategy"]; dispatch_count: number;
  selected_articles_artifact: string | null; api_timings: PlanRunRow["api_timings"];
  evaluated_at: string; selection_started_at_utc: string | null;
}) {
  const row = PlanRunRowSchema.parse({
    ...values, run_id: context.run_id, attempt: context.writer.attempt, date: context.date, started_at: context.captured_at,
    lifecycle_window_days: inputs.harvest.config.feedback.lifecycle_window_days,
    reliability_floor: inputs.clock_config.collect.reliability_floor,
    reliability_penalty_enabled: inputs.harvest.config.curate_articles.source_reliability_penalty_enabled,
    request_report_closed_days: inputs.harvest.config.feedback.request_report_closed_days,
    reliability_window_days: inputs.clock_config.collect.reliability_window_days,
  });
  const files = await persistLedger({
    ledger: "plan-runs", rowContract: PlanRunRowContract, rows: [row], registryEntry: inputs.registrations.plan_runs,
    outputRoot: inputs.outputRoot, writerContext: context.writer, ledgerSettings: inputs.ledgerSettings,
    period: { tier: "raw", covers: context.date },
  });
  if (files.status !== "written") throw new Error("Planner run outcome was not saved");
  return { row, files };
}
