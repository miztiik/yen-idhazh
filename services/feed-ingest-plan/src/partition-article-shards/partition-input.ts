/** Resolve only the configured worker strategy and worker-count bounds. */
import { FeedPartitionConfigSchema } from "@idhazh/common-contracts";
import { z } from "zod";

const StrategySchema = z.enum(["bin-pack", "round-robin", "none"]);
export type PartitionRequest = Readonly<{ strategy?: z.infer<typeof StrategySchema>; shards?: number }>;
export type ResolvedPartition = Readonly<{ strategy: z.infer<typeof StrategySchema>; dispatch_count: number }>;
export function resolvePartitionRequest(
  settings: z.input<typeof FeedPartitionConfigSchema>, request: PartitionRequest = {},
): ResolvedPartition {
  const config = FeedPartitionConfigSchema.parse(settings);
  const strategy = StrategySchema.parse(request.strategy ?? config.default_strategy);
  const count = request.shards ?? (strategy === "none" ? 1 : config.default_shards);
  if (!Number.isSafeInteger(count) || count < 1) throw new Error("shards must be a positive safe integer");
  if (strategy === "none") {
    if (count !== 1) throw new Error("none requires an omitted shard count or explicit one");
  } else if (count < config.min_shards || count > config.max_shards) {
    throw new Error(`shards must be within configured bounds ${config.min_shards}..${config.max_shards}`);
  }
  return { strategy, dispatch_count: count };
}
