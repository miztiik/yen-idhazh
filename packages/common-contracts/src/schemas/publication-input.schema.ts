/** Which existing publication fields name native files and their completed-write evidence? */
import { z } from "zod";
import { WriterIdentitySchema } from "./envelope.schema";
import { CountSchema, SchemaVersionSchema, Sha256Schema } from "./primitives";

// These are read projections of Python-owned contracts, not a new persisted format.
export const PUBLICATION_INVENTORY_VERSION = "2026-10-03T13:33";
export const PUBLICATION_RECEIPT_VERSION = "2026-10-09";
export const NativeRelativePathSchema = z.string().regex(
  /^[A-Za-z0-9._-]*[A-Za-z0-9_-][A-Za-z0-9._-]*(?:\/[A-Za-z0-9._-]*[A-Za-z0-9_-][A-Za-z0-9._-]*)*$/,
);
export const PublicationEntryInputSchema = z.strictObject({
  root: z.enum(["public", "state"]).default("public"),
  path: NativeRelativePathSchema, bytes: CountSchema, items: CountSchema,
});
export const PublicationInventoryInputSchema = z.object({
  version: SchemaVersionSchema, entries: z.array(PublicationEntryInputSchema).default([]),
}).superRefine((value, ctx) => {
  if (value.version !== PUBLICATION_INVENTORY_VERSION) {
    ctx.addIssue({ code: "custom", message: "publication inventory version differs from the native contract" });
  }
  const keys = value.entries.map(entry => `${entry.root}/${entry.path}`);
  if (keys.some((key, index) => index > 0 && keys[index - 1]! >= key)) {
    ctx.addIssue({ code: "custom", message: "publication entries must ascend without repeats" });
  }
});
export const PublicationReceiptInputSchema = z.object({
  version: SchemaVersionSchema, identity: WriterIdentitySchema,
  writes: z.record(NativeRelativePathSchema, Sha256Schema).default({}),
}).superRefine((value, ctx) => {
  if (value.version !== PUBLICATION_RECEIPT_VERSION) {
    ctx.addIssue({ code: "custom", message: "publication receipt version differs from the native contract" });
  }
});
export type PublicationInventoryInput = z.infer<typeof PublicationInventoryInputSchema>;
export type PublicationReceiptInput = z.infer<typeof PublicationReceiptInputSchema>;
