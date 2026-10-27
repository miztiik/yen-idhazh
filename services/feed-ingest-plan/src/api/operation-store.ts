/** Replay one indexed durable request without scanning or repeating completed work. */
import { Database } from "bun:sqlite";
import { mkdir } from "node:fs/promises";
import { join } from "node:path";
import { createHash } from "node:crypto";
import { PlanError } from "./plan-request";
import { PlannerOperationSchema, RequestIdSchema } from "./operation-contracts";
import type { PlannerOperation } from "./operation-contracts";
import { SourceArticleOutcomeSchema } from "@idhazh/common-contracts";
import type { SourceArticleOutcome } from "@idhazh/common-contracts";

type RequestIdentity = Pick<PlannerOperation, "request_id" | "operation" | "input_sha256" | "config_sha256">;
export type PreparedOperation = Readonly<RequestIdentity & { capture: () => PlannerOperation }>;

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
  function readRequest(proposed: RequestIdentity) {
    const previous = get(proposed.request_id);
    if (previous && (previous.operation !== proposed.operation
      || previous.input_sha256 !== proposed.input_sha256 || previous.config_sha256 !== proposed.config_sha256)) {
      throw new PlanError("REQUEST_CONFLICT", "Request key was already used with different input or configuration", "request_id");
    }
    return previous;
  }
  function settleSourceOutcome(id: string, outcome: SourceArticleOutcome): SourceArticleOutcome {
    const checked = SourceArticleOutcomeSchema.parse(outcome);
    try { database.exec("BEGIN IMMEDIATE"); }
    catch (error) { refuseBusy(error); }
    let committed = false;
    try {
      const capture = get(id);
      if (capture === null || capture.state !== "complete" || capture.operation !== "fetch"
        || capture.artifact?.fetch_item_type !== "article") {
        throw new PlanError("ARTIFACT_NOT_FOUND", "A source outcome requires its completed article capture", "fetch_request_id");
      }
      const settled = capture.source_outcome ?? checked;
      if (capture.source_outcome === null) put({ ...capture, source_outcome: settled });
      database.exec("COMMIT");
      committed = true;
      return settled;
    } finally { if (!committed && database.inTransaction) database.exec("ROLLBACK"); }
  }
  async function execute(
    proposed: PlannerOperation | PreparedOperation,
    work: (record: PlannerOperation) => Promise<Pick<PlannerOperation, "response_json" | "artifact"> & Partial<Pick<PlannerOperation, "source_outcome">>>,
  ): Promise<PlannerOperation> {
    try { database.exec("BEGIN IMMEDIATE"); }
    catch (error) { refuseBusy(error); }
    let committed = false;
    try {
      const previous = readRequest(proposed);
      if (previous?.state === "complete") {
        database.exec("COMMIT");
        committed = true;
        return previous;
      }
      if (previous !== null) {
        throw new PlanError("REQUEST_INCOMPLETE", "Started or interrupted request requires inspection before using a new request key", "request_id");
      }
      const record = previous ?? ("capture" in proposed ? proposed.capture() : proposed);
      for (const field of ["request_id", "operation", "input_sha256", "config_sha256"] as const) {
        if (record[field] !== proposed[field]) {
          throw new PlanError("INVALID_RUN_CONTEXT", "Captured request differs from its prepared input", field);
        }
      }
      // Claim once, then release the write lock before asynchronous network or parsing work.
      put(record);
      database.exec("COMMIT");
      committed = true;
      const result = await work(record);
      const complete = PlannerOperationSchema.parse({ ...record, ...result, state: "complete" });
      try { database.exec("BEGIN IMMEDIATE"); }
      catch (error) { refuseBusy(error); }
      committed = false;
      const parentId = complete.artifact?.parent_fetch_request_id;
      if (complete.artifact?.fetch_item_type === "article" && parentId != null) {
        const parent = get(parentId);
        if (parent?.state !== "complete" || parent.operation !== "fetch" || parent.artifact?.fetch_item_type !== "feed"
          || parent.run_id !== complete.run_id || parent.correlation_id !== complete.correlation_id) {
          throw new PlanError("ARTIFACT_INVALID", "Article capture lacks its original feed receipt", "fetch_request_id");
        }
        put({ ...parent, article_capture_request_ids: [...new Set([...parent.article_capture_request_ids, complete.request_id])] });
      }
      put(complete);
      database.exec("COMMIT");
      committed = true;
      return complete;
    } finally {
      if (!committed && database.inTransaction) database.exec("ROLLBACK");
    }
  }
  return { get, execute, settleSourceOutcome, close: () => database.close() };
}
export type OperationStore = Awaited<ReturnType<typeof openOperationStore>>;
