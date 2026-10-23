/** Which exact native files did this listener itself persist under its output root? */
import { realpath } from "node:fs/promises";
import { isAbsolute, relative, resolve } from "node:path";
import { z } from "zod";
import { DateStampSchema, FeedHealthContract, FeedRetirementContract, Sha256Schema } from "@idhazh/common-contracts";
import type { FeedHealthRow, FeedRetirementRow } from "@idhazh/common-contracts";
import type { LedgerRegistration, PersistedLedgerFile } from "@idhazh/ledger-file-writer";
import { RelativePathSchema } from "../config/service-settings";
import { readLedgerParquet } from "./read-parquet";
import type { ReadLedgerFile } from "./read-parquet";

const FilesSchema = z.array(RelativePathSchema).min(1)
  .refine(files => new Set(files).size === files.length, "own feed receipt files must be distinct");
export const OwnFeedReceiptSchema = z.discriminatedUnion("ledger", [
  z.strictObject({ ledger: z.literal("feed-health"), day: DateStampSchema, files: FilesSchema }),
  z.strictObject({
    ledger: z.literal("feed-retirements"), day: DateStampSchema, files: FilesSchema,
    endpoint_keys: z.array(Sha256Schema).min(1).refine(keys => new Set(keys).size === keys.length),
  }),
]);
export type OwnFeedReceipt = z.infer<typeof OwnFeedReceiptSchema>;
export type FeedWriteReceipt = Readonly<{
  ledger: "feed-health"; day: string; files: readonly PersistedLedgerFile[];
}> | Readonly<{
  ledger: "feed-retirements"; day: string; files: readonly PersistedLedgerFile[]; endpoint_keys: readonly string[];
}>;

export async function readOwnFeedReceipts(
  root: string, receipts: readonly OwnFeedReceipt[], now: string,
  registrations: { health: LedgerRegistration; retirements: LedgerRegistration },
) {
  const parsed = receipts.map(receipt => OwnFeedReceiptSchema.parse(receipt));
  const loaded: {
    receipt: OwnFeedReceipt; files: (ReadLedgerFile<FeedHealthRow> | ReadLedgerFile<FeedRetirementRow>)[];
  }[] = [];
  if (parsed.length === 0) return loaded;
  const base = await realpath(root);
  for (const receipt of parsed) {
    if (receipt.day > now.slice(0, 10)) throw new Error("Own feed receipt exceeds the captured UTC clock");
    const files = [];
    for (const path of receipt.files) {
      const target = await realpath(resolve(base, path));
      const local = relative(base, target);
      if (isAbsolute(local) || local === ".." || local.startsWith("../") || local.startsWith("..\\")) {
        throw new Error("Own feed receipt escapes its output root");
      }
      const file = receipt.ledger === "feed-health"
        ? await readLedgerParquet(target, receipt.ledger, FeedHealthContract)
        : await readLedgerParquet(target, receipt.ledger, FeedRetirementContract);
      const registration = receipt.ledger === "feed-health" ? registrations.health : registrations.retirements;
      const expected = ["raw", ...registration.prefix, ...receipt.day.split("-"), `${file.envelope.file_id}.parquet`].join("/");
      if (path !== expected || file.envelope.tier !== "raw" || file.envelope.covers !== receipt.day) {
        throw new Error("Own feed receipt differs from its native raw file identity");
      }
      if (file.rows.some(({ row }) => ("date" in row ? row.date : row.retired_on) !== receipt.day)) {
        throw new Error("Own feed row differs from its receipt UTC day");
      }
      files.push(file);
    }
    if (receipt.ledger === "feed-retirements") {
      const keys = files.flatMap(file => file.rows.flatMap(({ row }) => "endpoint_key" in row && row.endpoint_key !== null
        ? [row.endpoint_key] : []));
      if (new Set(keys).size !== receipt.endpoint_keys.length
        || receipt.endpoint_keys.some(key => !keys.includes(key))) {
        throw new Error("Own retirement receipt differs from its actual endpoint evidence");
      }
    }
    loaded.push({ receipt, files });
  }
  return loaded;
}
