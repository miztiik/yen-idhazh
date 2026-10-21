/** Writes each completed ledger file by temporary-file-plus-rename. */
import { randomUUID } from "node:crypto";
import { rename, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";

export async function writeAtomically(target: string, data: Uint8Array): Promise<void> {
  const temporary = join(dirname(target), `.${randomUUID()}.tmp`);
  try {
    await writeFile(temporary, data, { flag: "wx" });
    await rename(temporary, target);
  } catch (error) {
    try {
      await rm(temporary, { force: true });
    } catch (cleanupError) {
      throw new AggregateError([error, cleanupError], `could not complete or clean up ledger write ${target}`);
    }
    throw error;
  }
}
