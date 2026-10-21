/** Creates the repeatable work-unit identity used by ledger files. */
import { createHash } from "node:crypto";

const URL_NAMESPACE = "6ba7b811-9dad-11d1-80b4-00c04fd430c8";
const REPOSITORY_NAMESPACE_NAME = "github.com/miztiik/yen-idhazh";

function parseUuidBytes(value: string): Buffer {
  return Buffer.from(value.replaceAll("-", ""), "hex");
}

function formatUuid(value: Buffer): string {
  const hex = value.toString("hex");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function createUuidV5(namespace: Buffer, name: string): string {
  const digest = createHash("sha1").update(namespace).update(name, "utf8").digest();
  const value = Buffer.from(digest.subarray(0, 16));
  value[6] = (value[6]! & 0x0f) | 0x50;
  value[8] = (value[8]! & 0x3f) | 0x80;
  return formatUuid(value);
}

const REPOSITORY_NAMESPACE = createUuidV5(parseUuidBytes(URL_NAMESPACE), REPOSITORY_NAMESPACE_NAME);

export type UnitIdentity = {
  ledger: string;
  covers: string;
  runId: string;
  job: string | null;
  pipelineName: string | null;
  taskName: string | null;
  shard: number;
  producer: string;
};

export function createUnitId(identity: UnitIdentity): string {
  const generic = identity.pipelineName !== null || identity.taskName !== null;
  if (generic && (identity.pipelineName === null || identity.taskName === null)) {
    throw new Error("unit identity requires both pipeline_name and task_name");
  }
  if (!generic && identity.job === null) {
    throw new Error("unit identity requires legacy job or pipeline and task");
  }
  if (generic && identity.job !== null && identity.job !== identity.taskName) {
    throw new Error("generic job must be absent or match its task");
  }
  const label = generic ? `${identity.pipelineName}|${identity.taskName}` : identity.job!;
  const seed = `${identity.ledger}|${identity.covers}|${identity.runId}|${label}|${identity.shard}|${identity.producer}`;
  return createUuidV5(parseUuidBytes(REPOSITORY_NAMESPACE), seed);
}
