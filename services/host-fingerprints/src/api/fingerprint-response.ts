/** What can a completed fingerprint HTTP request truthfully report? */
import { z } from "zod";
import { HostFingerprintRowSchema } from "@idhazh/common-contracts";
import { PersistedLedgerFileSchema } from "@idhazh/ledger-file-writer";

export const FingerprintHealthSchema = z.strictObject({ status: z.literal("ok"), enabled: z.boolean() });
export const FingerprintWrittenSchema = z.strictObject({
  status: z.literal("written"), row: HostFingerprintRowSchema,
  unavailable: z.record(z.string(), z.string()),
  files: z.array(PersistedLedgerFileSchema.required({ unit_id: true })).length(1),
});
export const FingerprintResponseSchema = z.discriminatedUnion("status", [
  FingerprintWrittenSchema,
  z.strictObject({
    status: z.literal("disabled"), row: z.null(), files: z.tuple([]),
    unavailable: z.strictObject({}),
  }),
]);
export type FingerprintResponse = z.infer<typeof FingerprintResponseSchema>;
