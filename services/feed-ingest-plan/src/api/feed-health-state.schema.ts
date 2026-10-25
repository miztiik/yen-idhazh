/** Which operator request and update result may cross the feed-health state API? */
import { z } from "zod";
import {
  DateStampSchema, PositiveCountSchema, SelectionStateCaptureSchema,
} from "@idhazh/common-contracts";

export const FeedHealthStateUpdateRequestSchema = z.strictObject({
  batch_id: z.uuid({ version: "v4" }),
});

export const FeedHealthStateUpdateResponseSchema = z.strictObject({
  batch_id: z.uuid({ version: "v4" }),
  selection_state: SelectionStateCaptureSchema,
  update: z.strictObject({
    status: z.enum(["saved", "unchanged", "save_failed", "unavailable"]),
    state_revision: PositiveCountSchema.nullable(),
    attempted_revision: PositiveCountSchema.nullable(),
    parent_revision: PositiveCountSchema.nullable(),
    changed_days: z.array(DateStampSchema),
    diagnostics: z.array(z.enum([
      "input_gap", "correction_outside_window", "ancestor_unavailable",
      "stale_fallback", "previous_snapshot_used", "save_refused", "retry_exhausted",
    ])),
  }).superRefine((result, ctx) => {
    if (new Set(result.changed_days).size !== result.changed_days.length) {
      ctx.addIssue({ code: "custom", message: "changed_days must be distinct" });
    }
    if (result.status === "saved") {
      if (result.state_revision === null || result.attempted_revision !== result.state_revision
        || ((result.state_revision === 1) !== (result.parent_revision === null))
        || (result.parent_revision !== null && result.parent_revision + 1 !== result.state_revision)) {
        ctx.addIssue({ code: "custom", message: "saved state identifies its new revision and actual parent" });
      }
    } else if (result.status === "unchanged") {
      if (result.state_revision === null || result.attempted_revision !== null
        || result.parent_revision !== null || result.changed_days.length !== 0) {
        ctx.addIssue({ code: "custom", message: "unchanged state identifies the saved revision and no new work" });
      }
    } else if (result.status === "save_failed") {
      if (result.attempted_revision === null || result.state_revision !== result.parent_revision
        || ((result.attempted_revision === 1) !== (result.parent_revision === null))
        || (result.parent_revision !== null && result.parent_revision + 1 !== result.attempted_revision)) {
        ctx.addIssue({ code: "custom", message: "a failed save leaves its actual parent revision unchanged" });
      }
    } else if (result.state_revision !== null || result.attempted_revision !== null
      || result.parent_revision !== null) {
      ctx.addIssue({ code: "custom", message: "unavailable state has no saved or attempted revision" });
    }
  }),
});
