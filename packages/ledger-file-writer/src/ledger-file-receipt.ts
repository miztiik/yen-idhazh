/** Which exact completed file may a ledger writer return to its caller? */
import { z } from "zod";
import { CountSchema, FileEnvelopeSchema, Sha256Schema } from "@idhazh/common-contracts";

export const PersistedLedgerFileSchema = z.strictObject({
  path: z.string().min(1).refine(path => !path.includes("\\") && !path.startsWith("/")
    && !/[:\u0000-\u001f\u007f]/.test(path) && path.split("/").every(part => part !== "" && part !== "." && part !== ".."),
  "requires a relative POSIX file path"),
  file_id: FileEnvelopeSchema.shape.file_id,
  unit_id: FileEnvelopeSchema.shape.unit_id.optional(),
  covers: FileEnvelopeSchema.shape.covers,
  content_sha256: Sha256Schema,
  row_count: CountSchema,
});
