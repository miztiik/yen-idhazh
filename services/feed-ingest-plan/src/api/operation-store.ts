/** Replay one indexed durable request without scanning or repeating completed work. */
import { Database } from "bun:sqlite";
import { mkdir } from "node:fs/promises";
import { join } from "node:path";
import { createHash } from "node:crypto";
import { PlanError } from "./plan-request";
import { PlannerOperationSchema, RequestIdSchema } from "./operation-contracts";
import type { PlannerOperation } from "./operation-contracts";

export function sha256(value: string): string {
  return createHash("sha256").update(value).digest("hex");
}

export async function openOperationStore(outputRoot: string) {
  // The fixed filename and SQL schema are storage protocol constants, not tunables.
  await mkdir(outputRoot, { recursive: true });
  const database = new Database(join(outputRoot, "planner-operations.sqlite"), { create: true });
  const refuseBusy = (error: unknown): never => {
    if (error && typeof error === "object" && "code" in error && error.code === "SQLITE_BUSY") {
      throw new PlanError("REQUEST_BUSY", "Another process owns the operation store; retry the same request", "request_id");
    }
    throw error;
  };
  try {
    database.exec("PRAGMA journal_mode = WAL; PRAGMA synchronous = FULL;");
    database.exec("CREATE TABLE IF NOT EXISTS operations (request_id TEXT PRIMARY KEY, record TEXT NOT NULL)");
  } catch (error) {
    database.close();
    refuseBusy(error);
  }
  const read = database.query<{ record: string }, [string]>("SELECT record FROM operations WHERE request_id = ?");
  const write = database.query("INSERT OR REPLACE INTO operations (request_id, record) VALUES (?, ?)");
  function get(id: string): PlannerOperation | null {
    const row = read.get(RequestIdSchema.parse(id));
    return row === null ? null : PlannerOperationSchema.parse(JSON.parse(row.record));
  }
  function put(value: PlannerOperation) {
    const checked = PlannerOperationSchema.parse(value);
    write.run(checked.request_id, JSON.stringify(checked));
  }
  async function execute(
    proposed: PlannerOperation,
    work: (record: PlannerOperation) => Promise<Pick<PlannerOperation, "response_json" | "artifact">>,
  ): Promise<PlannerOperation> {
    try { database.exec("BEGIN IMMEDIATE"); }
    catch (error) { refuseBusy(error); }
    let committed = false;
    try {
      const previous = get(proposed.request_id);
      if (previous && (previous.operation !== proposed.operation
        || previous.input_sha256 !== proposed.input_sha256 || previous.config_sha256 !== proposed.config_sha256)) {
        throw new PlanError("REQUEST_CONFLICT", "Request key was already used with different input or configuration", "request_id");
      }
      if (previous?.state === "complete") {
        database.exec("COMMIT");
        committed = true;
        return previous;
      }
      if (previous?.operation === "plan") {
        throw new PlanError("REQUEST_INCOMPLETE", "Interrupted plan requires inspection of its recorded run before a new request", "request_id");
      }
      const record = previous ?? proposed;
      // Commit identity first; another process may win the next lock, but only its owner can do work.
      put(record);
      database.exec("COMMIT");
      try { database.exec("BEGIN IMMEDIATE"); }
      catch (error) { refuseBusy(error); }
      const result = await work(record);
      const complete = PlannerOperationSchema.parse({ ...record, ...result, state: "complete" });
      put(complete);
      database.exec("COMMIT");
      committed = true;
      return complete;
    } finally {
      if (!committed && database.inTransaction) database.exec("ROLLBACK");
    }
  }
  return { get, execute, close: () => database.close() };
}
export type OperationStore = Awaited<ReturnType<typeof openOperationStore>>;
