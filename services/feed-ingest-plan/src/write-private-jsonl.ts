/** Close and publish a validated JSONL prefix without exposing unfinished writes. */
import { lstat, mkdir, open, realpath, rename, rm } from "node:fs/promises";
import type { FileHandle } from "node:fs/promises";
import { join } from "node:path";
import { RelPathSchema } from "@idhazh/common-contracts";
import type { z } from "zod";

async function openPrivateFile(root: string, path: string) {
  const parts = RelPathSchema.parse(path).split("/");
  let parent = await realpath(root);
  for (const part of parts.slice(0, -1)) {
    parent = join(parent, part);
    await mkdir(parent, { recursive: true });
    const info = await lstat(parent);
    if (!info.isDirectory() || info.isSymbolicLink()) throw new Error("Private artifact parent is not a plain directory");
  }
  const target = join(parent, parts.at(-1)!);
  try {
    await lstat(target);
    throw new Error("Private artifact already exists for this execution");
  } catch (error) {
    if (!(error instanceof Error && "code" in error && error.code === "ENOENT")) throw error;
  }
  return { target, temporary: `${target}.part`, file: await open(`${target}.part`, "wx", 0o600) };
}

export function createPrivateJsonlWriter<T>(root: string, path: string, schema: z.ZodType<T>) {
  RelPathSchema.parse(`${path}.part`);
  let tail = Promise.resolve();
  let opened: { target: string; temporary: string; file: FileHandle } | undefined;
  let failure: unknown;
  let closing: Promise<void> | undefined;
  let completeBytes = 0;
  let records = 0;
  return {
    get records() { return records; },
    append(raw: unknown) {
      if (closing !== undefined) return Promise.reject(new Error("Private JSONL writer has finished"));
      const operation = tail.then(async () => {
        if (failure !== undefined) throw failure;
        const line = `${JSON.stringify(schema.parse(raw))}\n`;
        opened ??= await openPrivateFile(root, path);
        await opened.file.appendFile(line, "utf8");
        completeBytes += Buffer.byteLength(line, "utf8");
        records++;
      });
      tail = operation.catch(error => { failure ??= error; });
      return operation;
    },
    finish() {
      closing ??= (async () => {
        await tail;
        const failures: unknown[] = failure === undefined ? [] : [failure];
        if (opened !== undefined) {
          let validPrefix = true;
          try {
            await opened.file.truncate(completeBytes);
            await opened.file.sync();
          } catch (error) { validPrefix = false; failures.push(error); }
          try { await opened.file.close(); }
          catch (error) { validPrefix = false; failures.push(error); }
          if (validPrefix) {
            try {
              if (records > 0) await rename(opened.temporary, opened.target);
              else await rm(opened.temporary);
            } catch (error) { failures.push(error); }
          }
        }
        if (failures.length) throw new AggregateError(failures, "Private JSONL output did not complete");
      })();
      return closing;
    },
  };
}
