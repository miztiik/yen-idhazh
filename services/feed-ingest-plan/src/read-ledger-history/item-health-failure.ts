/** Which settled item failures must not be retried again on the same UTC day? */
import { z } from "zod";
import { DateStampSchema, ItemHealthFailureCodeSchema, Sha256Schema } from "@idhazh/common-contracts";
import type { LedgerRowProjectionContract } from "./read-parquet";
import { ITEM_HEALTH_ROW_SCHEMA_VERSION } from "./item-health-version";

export const ItemHealthFailureProjectionSchema = z.strictObject({
  date: DateStampSchema, url_key: Sha256Schema,
  outcome: z.enum(["ok", "failed"]), code: ItemHealthFailureCodeSchema.nullable(),
});
export type ItemHealthFailureProjection = z.infer<typeof ItemHealthFailureProjectionSchema>;
export const ItemHealthFailureProjectionContract: LedgerRowProjectionContract<ItemHealthFailureProjection> = {
  schema: ItemHealthFailureProjectionSchema,
  schemaVersion: ITEM_HEALTH_ROW_SCHEMA_VERSION,
  projectedFields: ["date", "url_key", "outcome", "code"],
};
