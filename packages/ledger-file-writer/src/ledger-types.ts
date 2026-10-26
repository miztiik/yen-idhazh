import type { RowIdentity, WriterIdentity } from "@idhazh/common-contracts";
import type { ArrowColumn } from "./parquet/arrow-builder";
import type { z } from "zod";

export type LedgerRowContract<T extends object> = {
  schema: z.ZodType<T>;
  schemaVersion: string;
  legacyVersions?: Readonly<Record<string, {
    schema: z.ZodType<object>;
    migrate: (row: object) => T;
  }>>;
};

export type LedgerRegistration = {
  name: string;
  family: string;
  grain: "raw-and-compact";
  lifecycle_status: "active" | "paused" | "retired";
  prefix: readonly string[];
};

export type LedgerSettings = {
  format: "parquet" | "json";
  compression_raw: "snappy" | "zstd" | "none";
  compression_compact: "snappy" | "zstd" | "none";
};

export type LedgerPeriod =
  | { tier: "raw"; covers: string }
  | { tier: "compact"; period: "daily" | "monthly" | "yearly"; covers: string; builtFrom: number };

export type StoredLedgerRow<T extends object> = {
  identity: RowIdentity;
  row: T;
};

export type LedgerWriteContext<T extends object> = {
  ledger: string;
  rowContract: LedgerRowContract<T>;
  outputRoot: string;
  writerContext?: WriterIdentity;
  /** Actual health-file finalization clock; never copied onto a planner row. */
  updatedAt?: string;
  registryEntry: LedgerRegistration;
  ledgerSettings: LedgerSettings;
};

export type PersistLedgerInput<T extends object> = LedgerWriteContext<T> & (
  | { period: Extract<LedgerPeriod, { tier: "raw" }>; partition_date?: string; rows: readonly T[] }
  | { period: Extract<LedgerPeriod, { tier: "compact" }>; rows: readonly (StoredLedgerRow<T> | T)[] }
);

export type ValidatedLedgerWrite<T extends object> = {
  input: PersistLedgerInput<T>;
  ledger: string;
  writerContext: WriterIdentity | null;
  planner: boolean;
  rowSchema: z.ZodType<object>;
  outputRoot: string;
  columns: ArrowColumn[];
};

export type PersistedLedgerFile = {
  path: string;
  file_id: string;
  /** Other families retain their work-unit identity; planner files have none. */
  unit_id?: string;
  covers: string;
  content_sha256: string;
  row_count: number;
};

export type PersistLedgerResult =
  | { status: "written"; files: PersistedLedgerFile[] }
  | { status: "empty"; files: [] }
  | {
      status: "skipped";
      reason: "ledger_not_active";
      files: [];
      warning: {
        event: "ledger_write_skipped";
        ledger: string;
        family: string;
        lifecycle_status: "paused" | "retired";
        row_count: number;
      };
    };
