/** What a published-site check asks TypeScript to validate for planner ledgers. */
import { z } from "zod";
import { CountSchema, RelPathSchema } from "./primitives";
import { PlannerLedgerNameSchema } from "./envelope.schema";

export const PLANNER_FILE_VALIDATION_VERSION = "2026-10-27" as const;

const PlannerFileInputSchema = z.strictObject({
  ledger: PlannerLedgerNameSchema,
  path: RelPathSchema,
}).superRefine((file, ctx) => {
  const prefix = `state/raw/feed-ingest-plan/${file.ledger}/`;
  const compactPrefix = `state/compact/feed-ingest-plan/${file.ledger}/`;
  if ((!file.path.startsWith(prefix) && !file.path.startsWith(compactPrefix))
    || !file.path.endsWith(".parquet")) {
    ctx.addIssue({
      code: "custom",
      message: "planner validation requires a registered planner Parquet path",
      path: ["path"],
    });
  }
});

export const PlannerFileValidationRequestSchema = z.strictObject({
  version: z.literal(PLANNER_FILE_VALIDATION_VERSION).default(PLANNER_FILE_VALIDATION_VERSION),
  files: z.array(PlannerFileInputSchema),
}).superRefine((request, ctx) => {
  const paths = request.files.map(file => file.path);
  if (new Set(paths).size !== paths.length) {
    ctx.addIssue({
      code: "custom",
      message: "planner validation file paths must be unique",
      path: ["files"],
    });
  }
});
export type PlannerFileValidationRequest = z.infer<typeof PlannerFileValidationRequestSchema>;

export const PlannerFileValidationResultSchema = z.strictObject({
  version: z.literal(PLANNER_FILE_VALIDATION_VERSION),
  files: z.array(z.strictObject({
    ledger: PlannerLedgerNameSchema,
    path: RelPathSchema,
    status: z.enum(["valid", "invalid"]),
    row_count: CountSchema.nullable(),
    reason: z.enum(["missing", "invalid"]).nullable(),
  })),
});
export type PlannerFileValidationResult = z.infer<typeof PlannerFileValidationResultSchema>;
