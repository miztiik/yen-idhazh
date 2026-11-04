/** Allocate the identity of one captured article input, independently of its address and operations. */
import { randomUUID } from "node:crypto";
import { CandidateIdSchema } from "./schemas/primitives";

export function createCandidateId(): string {
  return CandidateIdSchema.parse(randomUUID());
}
