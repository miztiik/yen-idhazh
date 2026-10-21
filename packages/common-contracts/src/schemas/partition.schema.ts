/** Which worker allocation is valid independently of writer shards? */
import { z } from "zod";
import { CountSchema, PositiveCountSchema, reject } from "./primitives";

export const PartitionAssignmentSchema = z.strictObject({
  strategy: z.enum(["bin-pack", "round-robin", "none"]),
  worker_assignment: CountSchema, dispatch_count: PositiveCountSchema,
}).superRefine((value, ctx) => {
  if (value.worker_assignment >= value.dispatch_count) reject(ctx, "worker_assignment must be below dispatch_count");
  if (value.strategy === "none" && (value.worker_assignment !== 0 || value.dispatch_count !== 1)) reject(ctx, "none requires one dispatch and worker zero");
});
export type PartitionAssignment = z.infer<typeof PartitionAssignmentSchema>;
