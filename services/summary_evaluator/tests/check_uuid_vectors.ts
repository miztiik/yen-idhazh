/** Compare named fixture seeds with the existing writer's actual UUIDv5 implementation. */
import { readFileSync } from "node:fs";
import { createUuidV5 } from "../../../packages/ledger-file-writer/src/uuid/name-id.ts";

const fixture = Bun.argv[2];
if (!fixture) throw new Error("Supply the named event-id-vectors.json fixture.");
const vectors: unknown = JSON.parse(readFileSync(fixture, "utf8"));
if (!Array.isArray(vectors)) throw new Error("UUID vectors must be an array.");
const result = vectors.map((vector: unknown) => {
  if (vector === null || typeof vector !== "object"
    || !("name" in vector) || typeof vector.name !== "string"
    || !("namespace" in vector) || typeof vector.namespace !== "string"
    || !("seed" in vector) || typeof vector.seed !== "string") {
    throw new Error("Each UUID vector needs a name, namespace and exact seed.");
  }
  return { name: vector.name, actual_uuid: createUuidV5(vector.namespace, vector.seed) };
});
console.log(JSON.stringify(result));
