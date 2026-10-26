/** Which five registered raw ledgers may this workflow publish? */
import { lstat, readFile, realpath } from "node:fs/promises";
import { join, resolve } from "node:path";
import { z } from "zod";
import {
  DateStampSchema, HostFingerprintRowSchema, HOST_FINGERPRINT_VERSION,
  PlannerLedgerNameSchema, WriterIdentitySchema,
} from "../../../packages/common-contracts/src/index";
import type { LedgerRegistration, LedgerRowContract } from "../../../packages/ledger-file-writer/src/index";
import { readLedgerParquet } from "../src/read-ledger-history/read-parquet";
import { readPlannerParquet } from "../src/read-ledger-history/read-planner-parquet";
import { plannerContracts } from "./feed-ingest-plan-verification";

export const ExecutionIdentitySchema = z.strictObject({
  run_id: WriterIdentitySchema.shape.run_id, attempt: WriterIdentitySchema.shape.attempt,
  git_sha: WriterIdentitySchema.shape.git_sha,
});
export type ExecutionIdentity = z.infer<typeof ExecutionIdentitySchema>;
const LedgerSchema = z.enum([...PlannerLedgerNameSchema.options, "host-fingerprint"]);
export type MetadataLedger = z.infer<typeof LedgerSchema>;
export type MetadataRegistrations = Readonly<Record<MetadataLedger, LedgerRegistration>>;
const RegistrySchema = z.object({
  families: z.array(z.object({
    name: z.string().min(1), lifecycle_status: z.enum(["active", "paused", "retired"]),
    ledgers: z.array(z.object({ name: z.string(), grain: z.string(), prefix: z.array(z.string()).nullable() })),
  })),
});

export async function readMetadataRegistrations(path: string | URL): Promise<MetadataRegistrations> {
  const registry = RegistrySchema.parse(await Bun.file(path).json());
  const entries = LedgerSchema.options.map(name => {
    const matches = registry.families.flatMap(family => family.ledgers.filter(ledger => ledger.name === name)
      .map(ledger => ({ ...ledger, family: family.name, lifecycle_status: family.lifecycle_status })));
    if (matches.length !== 1) throw new Error(`registrations.${name}: exactly one registered ledger is required`);
    const entry = matches[0]!;
    return [name, {
      ...entry, grain: z.literal("raw-and-compact").parse(entry.grain),
      prefix: z.array(z.string().regex(/^[a-z0-9][a-z0-9-]*$/)).min(1).parse(entry.prefix),
    }] as const;
  });
  const registration = (name: MetadataLedger) => entries.find(([key]) => key === name)![1];
  return {
    "discovered-articles": registration("discovered-articles"), "selected-articles": registration("selected-articles"),
    "feed-health-state": registration("feed-health-state"), "plan-runs": registration("plan-runs"),
    "host-fingerprint": registration("host-fingerprint"),
  };
}

export function hostWriter(identity: ExecutionIdentity) {
  return WriterIdentitySchema.parse({
    ...ExecutionIdentitySchema.parse(identity), job: null, pipeline_name: "feed-ingest-plan",
    task_name: "isolated-plan", shard: 0, producer: "telemetry.silicon",
  });
}

export function identifyMetadataPath(path: string, registrations: MetadataRegistrations) {
  const name = LedgerSchema.options.find(name => path.startsWith(`raw/${registrations[name].prefix.join("/")}/`));
  if (name === undefined) throw new Error("commit: expected one exact current planner or host raw UUID Parquet path");
  const registration = registrations[name];
  if (registration.name !== name || registration.lifecycle_status !== "active"
    || registration.grain !== "raw-and-compact" || registration.prefix.some(part => !/^[a-z0-9][a-z0-9-]*$/.test(part))) {
    throw new Error("commit: metadata registration is not active and declared");
  }
  const suffix = path.slice(`raw/${registration.prefix.join("/")}/`.length).split("/");
  const file = suffix[3];
  if (suffix.length !== 4 || file === undefined
    || !/^[0-9a-f]{8}-[0-9a-f]{4}-8[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.parquet$/.test(file)) {
    throw new Error("commit: expected one exact current planner or host raw UUID Parquet path");
  }
  const covers = DateStampSchema.parse(suffix.slice(0, 3).join("-"));
  return { ledger: name, covers, file_id: file.slice(0, -8), indexed: name !== "host-fingerprint" };
}

export async function readMetadataBytes(root: string, path: string) {
  if (path.startsWith("/") || /[:\\\u0000-\u001f\u007f]/.test(path)
    || path.split("/").some(part => part === "" || part === "." || part === "..")) throw new Error("commit: output escapes state root");
  let file = await realpath(root);
  const parts = path.split("/");
  for (const [index, part] of parts.entries()) {
    file = join(file, part);
    const info = await lstat(file);
    if (info.isSymbolicLink() || !(index === parts.length - 1 ? info.isFile() : info.isDirectory())) {
      throw new Error("commit: output contains a symlink or non-file parent");
    }
  }
  if (resolve(await realpath(file)) !== resolve(file)) throw new Error("commit: output escapes state root");
  return { file, bytes: await readFile(file) };
}

export async function verifyMetadataFile(root: string, path: string, registrations: MetadataRegistrations, identity: ExecutionIdentity) {
  const expected = ExecutionIdentitySchema.parse(identity);
  const named = identifyMetadataPath(path, registrations);
  const { file, bytes } = await readMetadataBytes(root, path);
  const digest = Bun.CryptoHasher.hash("sha256", bytes, "hex");
  if (named.ledger === "host-fingerprint") {
    const actual = await readLedgerParquet(file, named.ledger, {
      schema: HostFingerprintRowSchema, schemaVersion: HOST_FINGERPRINT_VERSION,
    });
    const writer = hostWriter(expected);
    if (actual.file_sha256 !== digest || actual.envelope.tier !== "raw" || actual.envelope.covers !== expected.run_id.slice(0, 10)
      || actual.envelope.covers !== named.covers || actual.envelope.file_id !== named.file_id
      || actual.rows.length !== 1 || actual.rows[0]!.row.date !== named.covers
      || Object.entries(writer).some(([key, value]) => actual.envelope.identity[key as keyof typeof writer] !== value)) {
      throw new Error("commit: host output differs from its current execution identity");
    }
    return { ...named, bytes, file_sha256: digest, envelope: actual.envelope, rows: actual.rows.map(stored => stored.row),
      content_sha256: actual.envelope.content_sha256, row_count: actual.rows.length };
  }
  const contract: LedgerRowContract<object> = plannerContracts[named.ledger];
  const actual = await readPlannerParquet(file, named.ledger, contract);
  if (actual.file_sha256 !== digest || actual.envelope.tier !== "raw" || actual.envelope.covers !== named.covers
    || actual.envelope.file_id !== named.file_id || actual.envelope.row_schema_version !== contract.schemaVersion
    || actual.rows.length === 0 || (named.ledger !== "discovered-articles"
      && actual.rows.some(row => !("run_id" in row) || row.run_id !== expected.run_id
        || !("attempt" in row) || row.attempt !== expected.attempt))) {
    throw new Error("commit: planner output differs from its current execution identity");
  }
  return { ...named, bytes, file_sha256: digest, envelope: actual.envelope, rows: actual.rows,
    content_sha256: actual.envelope.content_sha256, row_count: actual.rows.length };
}
