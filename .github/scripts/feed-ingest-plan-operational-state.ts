/** Rebuild only derived planner state from one exact fresh committed base. */
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { relative, resolve, join } from "node:path";
import { isDeepStrictEqual } from "node:util";
import { LedgerNameSchema } from "../../packages/common-contracts/src/index";
import type { DocumentObservationRecord, WriterIdentity } from "../../packages/common-contracts/src/index";
import { persistLedger } from "../../packages/ledger-file-writer/src/index";
import type { LedgerRegistration, LedgerRowContract } from "../../packages/ledger-file-writer/src/index";
import { OperationalStateContract, DocumentObservationContract } from "../../services/feed-ingest-plan/src/metrics/audit-contracts";
import type { PlanInputs } from "../../services/feed-ingest-plan/src/load-plan-inputs";
import { closedObservationDays, readIngestEvidence } from "../../services/feed-ingest-plan/src/read-ledger-history/read-ingest-evidence";
import { readOperationalState } from "../../services/feed-ingest-plan/src/read-ledger-history/read-operational-state";
import type { LedgerHistoryReadSource } from "../../services/feed-ingest-plan/src/read-ledger-history/named-days";
import { readLedgerParquet, readLedgerParquetBytes } from "../../services/feed-ingest-plan/src/read-ledger-history/read-parquet";
import {
  buildOperationalStateRows, renderOperationalStateSnapshots,
} from "../../services/feed-ingest-plan/src/write-operational-state";
import { completeHistoryDayInputs } from "./feed-ingest-plan-outputs";
import type { PreparedPlannerState } from "./feed-ingest-plan-commit";

function missingFile(): Error {
  return Object.assign(new Error("Named committed ledger file is absent"), { code: "ENOENT" });
}

export function createFreshOperationalStatePreparation(input: Readonly<{
  repository: string; state_root: string; current_files: readonly string[];
  inputs: PlanInputs; writer: WriterIdentity;
}>) {
  return async (baseInput: Readonly<{
    base: string; now: string; read_file: (path: string) => Promise<Uint8Array | undefined>;
  }>): Promise<PreparedPlannerState> => {
    let outputRoot: string | undefined;
    try {
      const policy = input.inputs.harvest.config.feedback;
      const days = closedObservationDays(baseInput.now, policy.window_days);
      const observationDays = completeHistoryDayInputs(
        input.inputs.registrations.document_observations.prefix, days,
        input.inputs.settings.inputs.document_observation_days, "document_observation_days",
      );
      const source = <T extends object>(
        registration: LedgerRegistration, contract: LedgerRowContract<T>,
      ): LedgerHistoryReadSource<T> => ({
        readIndex: async path => baseInput.read_file(relative(input.repository, path).replaceAll("\\", "/")),
        readFile: async path => {
          const bytes = await baseInput.read_file(relative(input.repository, path).replaceAll("\\", "/"));
          if (bytes === undefined) throw missingFile();
          return readLedgerParquetBytes(bytes, path, LedgerNameSchema.parse(registration.name), contract);
        },
      });
      const observationSource = source<DocumentObservationRecord>(
        input.inputs.registrations.document_observations, DocumentObservationContract,
      );
      const stateSource = source(
        input.inputs.registrations.operational_state, OperationalStateContract,
      );
      const additionalRows: DocumentObservationRecord[] = [];
      const prefix = `raw/${input.inputs.registrations.document_observations.prefix.join("/")}/`;
      for (const path of input.current_files.filter(path => path.startsWith(prefix))) {
        const loaded = await readLedgerParquet(
          resolve(input.state_root, ...path.split("/")), "document-observations", DocumentObservationContract,
        );
        additionalRows.push(...loaded.rows.map(held => held.row));
      }
      const [evidence, saved] = await Promise.all([
        readIngestEvidence({
          root: input.repository, now: baseInput.now, window_days: policy.window_days,
          registration: input.inputs.registrations.document_observations, days: observationDays,
          read_source: observationSource, additional_rows: additionalRows,
        }),
        readOperationalState({
          root: input.state_root, snapshot_root: resolve(input.repository, "state"),
          now: baseInput.now, policy, registration: input.inputs.registrations.operational_state,
          read_source: stateSource,
        }),
      ]);
      if (!saved.writable) return { status: "not_written", reason: "saved_state_read_failed", files: [] };
      if (evidence.availability !== "available") {
        return { status: "not_written", reason: "history_unavailable", files: [] };
      }
      const rows = buildOperationalStateRows({
        evidence, now: baseInput.now, writer: input.writer, policy,
        parent_revision: saved.latest_revision,
      });
      if (rows.length === 0) return { status: "not_written", reason: "known_empty", files: [] };
      outputRoot = await mkdtemp(join(tmpdir(), "planner-operational-state-"));
      const writer = {
        ...input.writer, task_name: `operational-state-${baseInput.base.slice(0, 12)}`,
      };
      const result = await persistLedger({
        ledger: "operational-state", registryEntry: input.inputs.registrations.operational_state,
        rowContract: OperationalStateContract, outputRoot, writerContext: writer,
        ledgerSettings: input.inputs.ledgerSettings,
        period: { tier: "raw", covers: baseInput.now.slice(0, 10) }, rows,
      });
      if (result.status !== "written" || result.files.length !== 1) {
        throw new Error("Fresh-base operational state did not produce one native Parquet file");
      }
      const file = result.files[0]!;
      const readback = await readLedgerParquet(resolve(outputRoot, ...file.path.split("/")),
        "operational-state", OperationalStateContract);
      if (!isDeepStrictEqual(readback.rows.map(held => held.row), rows)) {
        throw new Error("Fresh-base operational state differs from its native readback");
      }
      const snapshots = await renderOperationalStateSnapshots({
        rows, ...(saved.latest_snapshot_rows === undefined ? {} : { previous_rows: saved.latest_snapshot_rows }),
        writer, inputs: input.inputs,
      });
      return {
        status: "written", reason: "none",
        files: [
          { path: file.path, bytes: await readFile(resolve(outputRoot, ...file.path.split("/"))) },
          ...snapshots,
        ],
      };
    } catch (error) {
      console.error(JSON.stringify({
        event: "operational_state_fresh_base_failed",
        diagnostic: error instanceof Error ? error.message : "unknown_error",
      }));
      return { status: "not_written", reason: "fresh_base_rebuild_failed", files: [] };
    } finally {
      if (outputRoot !== undefined) await rm(outputRoot, { recursive: true, force: true });
    }
  };
}
