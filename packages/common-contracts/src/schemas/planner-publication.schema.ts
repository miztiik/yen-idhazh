/** Which current planner files and derived index coverage may one site build publish? */
import { z } from "zod";
import { PlannerLedgerNameSchema } from "./envelope.schema";
import { CompactIndexSchema } from "./ledger-index.schema";
import { RelPathSchema, SchemaVersionSchema } from "./primitives";

const FileSchema = z.strictObject({ ledger: PlannerLedgerNameSchema, path: RelPathSchema }).superRefine((file, ctx) => {
  if (!file.path.startsWith(`compact/feed-ingest-plan/${file.ledger}/`) || !file.path.endsWith(".parquet")) {
    ctx.addIssue({ code: "custom", message: "Planner publication requires its exact compact Parquet path" });
  }
});
export const PlannerPublicationRequestSchema = z.strictObject({
  files: z.array(FileSchema), indexes: z.record(RelPathSchema, CompactIndexSchema),
}).superRefine((request, ctx) => {
  if (new Set(request.files.map(file => file.path)).size !== request.files.length) {
    ctx.addIssue({ code: "custom", message: "Planner publication files must be unique" });
  }
  for (const [path, index] of Object.entries(request.indexes)) {
    if (!PlannerLedgerNameSchema.safeParse(index.ledger).success
      || path !== `compact/feed-ingest-plan/${index.ledger}/index/${index.period}.json`) {
      ctx.addIssue({ code: "custom", message: "Planner publication index differs from its declared path" });
    }
  }
});
export const PlannerPublicationResultSchema = z.strictObject({
  files: z.array(RelPathSchema), indexes: z.record(RelPathSchema, CompactIndexSchema),
  refused: z.array(z.strictObject({
    ledger: PlannerLedgerNameSchema, path: RelPathSchema,
    envelope_version: SchemaVersionSchema, row_schema_version: SchemaVersionSchema,
  })),
});
export type PlannerPublicationResult = z.infer<typeof PlannerPublicationResultSchema>;
