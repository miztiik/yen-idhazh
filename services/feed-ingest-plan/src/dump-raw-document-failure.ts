/** Append failed raw documents locally and finish their writer before artifact delivery. */
import { lstat, mkdir, open, realpath } from "node:fs/promises";
import type { FileHandle } from "node:fs/promises";
import { join } from "node:path";
import { RawDocumentFailureSchema } from "@idhazh/common-contracts";
import type { RawDocumentFailure } from "@idhazh/common-contracts";
import type { PlanInputs } from "./load-plan-inputs";
import type { RunContext } from "./resolve-run-context";
import { rawDocumentContentsPath } from "./selected-artifact-path";
import { describePlanError } from "./api/plan-request";
import { writeJsonLine } from "./logging/structured-logger";

type FailureInput = Omit<RawDocumentFailure, "schema_version">;

async function openFailureFile(inputs: PlanInputs, context: RunContext): Promise<FileHandle> {
  const parts = rawDocumentContentsPath(inputs.settings.inputs.artifact_root, context).split("/");
  let parent = await realpath(inputs.root);
  for (const part of parts.slice(0, -1)) {
    parent = join(parent, part);
    await mkdir(parent, { recursive: true });
    const info = await lstat(parent);
    if (!info.isDirectory() || info.isSymbolicLink()) throw new Error("Raw document artifact parent is not a plain directory");
  }
  return open(join(parent, parts.at(-1)!), "ax", 0o600);
}

function createFailureWriter(inputs: PlanInputs, context: RunContext) {
  let tail = Promise.resolve();
  let file: FileHandle | undefined;
  let failure: unknown;
  let closing: Promise<void> | undefined;
  return {
    append(raw: FailureInput) {
      if (closing !== undefined) {
        const error = new Error("Raw document writer has finished");
        failure ??= error;
        return Promise.reject(error);
      }
      const operation = tail.then(async () => {
        const record = RawDocumentFailureSchema.parse(raw);
        file ??= await openFailureFile(inputs, context);
        await file.appendFile(`${JSON.stringify(record)}\n`, "utf8");
      });
      tail = operation.catch(error => { failure ??= error; });
      return operation;
    },
    finish() {
      closing ??= (async () => {
        await tail;
        const failures: unknown[] = failure === undefined ? [] : [failure];
        try { await file?.close(); }
        catch (error) { failures.push(error); }
        if (failures.length) throw new AggregateError(failures, "Raw document artifact writing failed");
      })();
      return closing;
    },
  };
}

const writers = new WeakMap<PlanInputs, Map<string, ReturnType<typeof createFailureWriter>>>();
const executionKey = (context: RunContext) => `${context.run_id}:${context.writer.attempt}`;

export async function dumpRawDocumentFailure(inputs: PlanInputs, context: RunContext, raw: FailureInput) {
  if (!inputs.settings.dump_raw_document_contents) return;
  let current = writers.get(inputs);
  if (current === undefined) { current = new Map(); writers.set(inputs, current); }
  const key = executionKey(context);
  let writer = current.get(key);
  if (writer === undefined) { writer = createFailureWriter(inputs, context); current.set(key, writer); }
  try { await writer.append(raw); }
  catch (error) {
    writeJsonLine({ event: "planner_raw_document_append_failed", code: describePlanError(error, inputs.root).code });
  }
}

export async function finishRawDocumentFailures(inputs: PlanInputs, context?: RunContext) {
  const current = writers.get(inputs);
  if (current === undefined) return;
  const key = context === undefined ? undefined : executionKey(context);
  const writer = key === undefined ? undefined : current.get(key);
  const selected = key === undefined ? [...current] : writer === undefined ? [] : [[key, writer] as const];
  const results = await Promise.allSettled(selected.map(([, writer]) => writer.finish()));
  const failures: unknown[] = [];
  for (const [index, result] of results.entries()) {
    current.delete(selected[index]![0]);
    if (result.status === "rejected") {
      failures.push(result.reason);
      writeJsonLine({ event: "planner_raw_document_finish_failed", code: describePlanError(result.reason, inputs.root).code });
    }
  }
  if (failures.length) throw new AggregateError(failures, "Raw document artifact preparation failed");
}
