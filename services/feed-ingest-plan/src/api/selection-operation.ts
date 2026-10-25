/** Which saved parsed batch produces one new combined screening and selection result? */
import { randomUUID } from "node:crypto";
import {
  OperationalStateReadSchema, ParsedFeedBatchSchema, SelectedFeedBatchSchema, StageReferenceRequestSchema,
  readParsedFeedBatch,
} from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import { operationConfigFingerprint } from "./document-operations";
import { PlanError } from "./plan-request";
import { readStageBatch, writeStageBatch } from "./stage-store";
import { selectArticles } from "../select-articles";
import type { ScreeningResult } from "../screen-article-candidates/triage-gates";
import { utcTimestamp } from "../harvest-feeds/harvest-types";

export function requireStageConfiguration(
  batch: { config_sha256: string }, inputs: PlanInputs, runtime: PlanRuntime,
) {
  if (!inputs.settings.enabled) throw new PlanError("PLANNER_DISABLED", "Planner is disabled by service settings", "enabled");
  if (batch.config_sha256 !== operationConfigFingerprint(inputs, runtime)) {
    throw new PlanError("REQUEST_CONFLICT", "Batch configuration differs from the current planner", "batch_id");
  }
}

export async function executeSelection(
  raw: unknown, inputs: PlanInputs, runtime: PlanRuntime, onScreened?: (result: ScreeningResult) => void,
) {
  const request = StageReferenceRequestSchema.parse(raw);
  const parsed = await readStageBatch(inputs.outputRoot, "parsed", request.batch_id, ParsedFeedBatchSchema, readParsedFeedBatch);
  requireStageConfiguration(parsed, inputs, runtime);
  const selectionStartedAtUtc = utcTimestamp(runtime.selection_clock ?? runtime.clock);
  const selectionState = OperationalStateReadSchema.parse({
    status: "unavailable", state_revision: null, notices: ["restrictions_unverified"],
    lifecycle_window_days: inputs.harvest.config.feedback.lifecycle_window_days,
    lifecycle_window_start: null, lifecycle_window_end: null,
    request_window_days: inputs.harvest.config.feedback.window_days,
    request_window_start: null, request_window_end: null,
  });
  const result = await selectArticles(parsed, inputs, onScreened);
  const batch = await writeStageBatch(inputs.outputRoot, "selected", SelectedFeedBatchSchema, {
    batch_id: randomUUID(), parsed_batch_id: parsed.batch_id,
    config_sha256: parsed.config_sha256, context: parsed.context,
    selection_state: {
      capture_status: "captured",
      selection_started_at_utc: selectionStartedAtUtc,
      state: selectionState,
    },
    selections: result.curation.rows,
    rejections: [...parsed.rejections, ...result.screening.rejections, ...result.curation.rejections],
  });
  return { batch, ...result };
}
