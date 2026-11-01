/** Prepare only the health evidence needed before fetch or during selection. */
import type { PlanInputs } from "../load-plan-inputs";
import { summarizePlanningHealth } from "../read-ledger-history/health-summary";
import { summarizeFeedAvailability } from "../availability/feed-availability-view";
import { projectFeedHealthFields } from "../read-ledger-history/read-feed-health-fields";
import { healthHistoryInput, readPlanningHistory } from "../read-ledger-history/read-run-history";
import type { CurrentHealthWork, RunHistory } from "../read-ledger-history/read-run-history";
import { PlanError } from "./plan-request";
export { healthHistoryInput } from "../read-ledger-history/read-run-history";
export type { CurrentHealthWork } from "../read-ledger-history/read-run-history";
export async function preparePlanningHealth(
  inputs: PlanInputs, now: string, current?: CurrentHealthWork, baseline?: RunHistory["health"],
) {
  const input = healthHistoryInput(inputs, now, current);
  if (current !== undefined && baseline === undefined) {
    throw new PlanError("ARTIFACT_NOT_FOUND", "Health work requires its live captured input", "batch_id");
  }
  const captured = structuredClone(baseline ?? await readPlanningHistory(inputs, now));
  const result = current === undefined ? captured : {
    ...captured, ...summarizePlanningHealth({ ...captured, ...input,
      saved_sources: captured.sources, current_rows: current.rows }),
  };
  const sources = new Map(result.sources);
  const requestRows = (current?.rows ?? []).flatMap(row => projectFeedHealthFields(row.date, [row]).request_totals.rows);
  const uses = { ...result.uses, request_totals: {
    ...result.uses.request_totals, rows: [...result.uses.request_totals.rows, ...requestRows],
  } };
  if (captured.input_gap) {
    for (const [id, source] of sources) sources.set(id, {
      ...source, article_pass_rate: null,
      reliability: source.reliability === null ? null : { ...source.reliability, complete: false },
    });
  }
  return { ...result, sources, uses, availability: summarizeFeedAvailability(sources, now, inputs.harvest.sources) };
}
