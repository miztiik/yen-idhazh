/** Create an RFC 4122 UUIDv5 from a namespace and a stable name. */
import { createHash } from "node:crypto";
import { z } from "zod";

export function createUuidV5(namespace: string, name: string): string {
  const digest = createHash("sha1")
    .update(Buffer.from(z.uuid().parse(namespace).replaceAll("-", ""), "hex")).update(name, "utf8").digest();
  const value = Buffer.from(digest.subarray(0, 16));
  value[6] = (value[6]! & 0x0f) | 0x50;
  value[8] = (value[8]! & 0x3f) | 0x80;
  const hex = value.toString("hex");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
