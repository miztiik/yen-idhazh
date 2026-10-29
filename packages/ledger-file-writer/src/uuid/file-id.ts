/** Creates the UUIDv8 identity used as one physical ledger file's name. */
import { createHash, randomBytes } from "node:crypto";

const CLOCK_MASK = (1n << 48n) - 1n;
const RAND_A_MASK = (1n << 12n) - 1n;
const RAND_B_MASK = (1n << 62n) - 1n;

export type FileIdentity = {
  unit: string;
  attempt: number;
  writtenAtMs: number;
};

export function createRejectedRawFileId(schemaVersion: string, day: string, contentSha256: string): string {
  const bytes = createHash("sha256")
    .update(JSON.stringify(["rejected-articles", schemaVersion, day, contentSha256]), "utf8")
    .digest().subarray(0, 16);
  bytes[6] = (bytes[6]! & 0x0f) | 0x80;
  bytes[8] = (bytes[8]! & 0x3f) | 0x80;
  const hex = bytes.toString("hex");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function createPlannerFileId(writtenAtMs: number): string {
  if (!Number.isSafeInteger(writtenAtMs) || writtenAtMs < 0) {
    throw new RangeError("file clock must be a nonnegative safe integer");
  }
  const bytes = randomBytes(16);
  bytes.writeUIntBE(writtenAtMs, 0, 6);
  bytes[6] = (bytes[6]! & 0x0f) | 0x80;
  bytes[8] = (bytes[8]! & 0x3f) | 0x80;
  const hex = bytes.toString("hex");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function createFileId(identity: FileIdentity): string {
  if (!Number.isSafeInteger(identity.attempt) || identity.attempt < 1) {
    throw new RangeError("attempt must be a positive safe integer");
  }
  if (!Number.isSafeInteger(identity.writtenAtMs) || identity.writtenAtMs < 0) {
    throw new RangeError("written_at_ms must be a nonnegative safe integer");
  }

  const digest = createHash("sha256")
    .update(`${identity.unit}|${identity.attempt}|${identity.writtenAtMs}`, "utf8")
    .digest();
  const clock = BigInt(identity.writtenAtMs) & CLOCK_MASK;
  const randA = BigInt(digest.readUInt16BE(0)) & RAND_A_MASK;
  const randB = BigInt(`0x${digest.subarray(2, 10).toString("hex")}`) & RAND_B_MASK;
  const value = (clock << 80n) | (8n << 76n) | (randA << 64n) | (2n << 62n) | randB;
  const hex = value.toString(16).padStart(32, "0");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
