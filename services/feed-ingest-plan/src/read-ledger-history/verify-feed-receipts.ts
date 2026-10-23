/** Do the named native receipt bytes and raw identities belong to the expected invocation? */
import { createHash } from "node:crypto";
import { readFile, realpath } from "node:fs/promises";
import { isAbsolute, relative, resolve } from "node:path";
import type { LedgerRowContract } from "@idhazh/ledger-file-writer";
import type { FeedReceiptWrite } from "./read-feed-inventory";
import { readLedgerParquet } from "./read-parquet";
import type { LedgerRowProjectionContract } from "./read-parquet";

export async function verifyFeedReceiptWrites<T extends object>(input: Readonly<{
  root: string;
  ledger: "feed-health" | "feed-retirements";
  contract: LedgerRowContract<T> | LedgerRowProjectionContract<T>;
  writes: readonly FeedReceiptWrite[];
}>): Promise<void> {
  if (input.writes.length === 0) return;
  const root = await realpath(input.root);
  for (const write of input.writes) {
    const path = await realpath(resolve(root, ...write.path.split("/")));
    const held = relative(root, path);
    if (isAbsolute(held) || held === ".." || held.startsWith("../") || held.startsWith("..\\")) {
      throw new Error("feed receipt: named native file escapes the input root");
    }
    const bytes = await readFile(path);
    if (createHash("sha256").update(bytes).digest("hex") !== write.sha256) {
      throw new Error("feed receipt: completed native file hash differs from its exact receipt");
    }
    const file = await readLedgerParquet(path, input.ledger, input.contract);
    if (file.envelope.tier !== "raw" || file.envelope.covers !== write.day) {
      throw new Error("feed receipt: completed native file has another tier or UTC day");
    }
    if (!write.path.endsWith(`/${file.envelope.file_id}.parquet`)) {
      throw new Error("feed receipt: named raw filename differs from its native file identity");
    }
    // The wrapper records execution identity; the actual producer retains its own module name.
    for (const field of ["run_id", "attempt", "job", "pipeline_name", "task_name", "shard", "git_sha"] as const) {
      if (file.envelope.identity[field] !== write.identity[field]) {
        throw new Error("feed receipt: completed native file belongs to another invocation");
      }
    }
  }
}
