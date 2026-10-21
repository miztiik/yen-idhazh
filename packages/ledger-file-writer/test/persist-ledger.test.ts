/** Verifies atomic file replacement and cleanup after an interrupted write. */
import { mkdir, mkdtemp, readdir, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { describe, expect, test } from "bun:test";
import { writeAtomically } from "../src/atomic-file";

describe("atomic ledger file writes", () => {
  test("removes a temporary file when the final rename is interrupted", async () => {
    const root = await mkdtemp(join(tmpdir(), "ledger-file-write-interrupt-"));
    const target = join(root, "blocked.parquet");
    try {
      await mkdir(target);
      await expect(writeAtomically(target, Buffer.from("PAR1"))).rejects.toThrow();
      expect(await readdir(root)).toEqual(["blocked.parquet"]);
      expect(await readdir(target)).toEqual([]);
    } finally {
      await rm(root, { recursive: true, force: true });
    }
  });

  test("does not replace an existing destination before writing its temporary file", async () => {
    const root = await mkdtemp(join(tmpdir(), "ledger-file-write-existing-"));
    const target = join(root, "existing.parquet");
    try {
      await writeFile(target, "old");
      await writeAtomically(target, Buffer.from("new"));
      expect(await Bun.file(target).text()).toBe("new");
      expect(await readdir(root)).toEqual(["existing.parquet"]);
    } finally {
      await rm(root, { recursive: true, force: true });
    }
  });
});
