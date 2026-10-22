/** Which native publication-row fields are stable enough for a bounded read? */
import {
  PUBLISHED_ROW_SCHEMA_VERSION,
  PublishedRowSchema,
} from "../metrics/publication-evidence";
import type { PublishedRow } from "../metrics/publication-evidence";
import type { LedgerRowProjectionContract } from "./read-parquet";

export const PublishedRowProjectionContract: LedgerRowProjectionContract<PublishedRow> = {
  schema: PublishedRowSchema,
  schemaVersion: PUBLISHED_ROW_SCHEMA_VERSION,
  projectedFields: ["version", "url_key", "published_on", "item_id"],
};
