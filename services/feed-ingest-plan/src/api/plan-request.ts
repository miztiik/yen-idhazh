/** Which API and CLI controls are valid before a feed can be requested? */
import { z } from "zod";
import { relative } from "node:path";
import { PositiveCountSchema, PositiveSchema } from "@idhazh/common-contracts";
import type { FeedIngestConfig } from "@idhazh/common-contracts";
import { resolvePartitionRequest } from "../partition-article-shards/partition-input";

export const PlanRequestSchema = z.strictObject({
  freshness_hours: PositiveSchema.optional(),
  article_limit: PositiveCountSchema.optional(),
  shards: PositiveCountSchema.optional(),
  partition_strategy: z.enum(["bin-pack", "round-robin", "none"]).optional(),
});
export type PlanRequest = z.infer<typeof PlanRequestSchema>;
export class PlanError extends Error {
  constructor(readonly code: string, message: string, readonly field: string | null = null) {
    super(message);
    this.name = "PlanError";
  }
}

export function resolvePlanRequest(raw: unknown, config: FeedIngestConfig) {
  const request = PlanRequestSchema.parse(raw);
  let partition;
  try {
    partition = resolvePartitionRequest(config.partition, {
      ...(request.partition_strategy === undefined ? {} : { strategy: request.partition_strategy }),
      ...(request.shards === undefined ? {} : { shards: request.shards }),
    });
  } catch (error) {
    if (!(error instanceof Error)) throw error;
    throw new PlanError("INVALID_REQUEST", error.message, "shards");
  }
  return {
    ...request, shards: partition.dispatch_count, partition_strategy: partition.strategy,
    article_limit: request.article_limit ?? config.curate.article_limit,
  };
}

export function parseCliRequest(args: readonly string[]) {
  const raw: Record<string, unknown> = {};
  let mode: "cli" | "serve" | undefined;
  const fields = new Set(["freshness_hours", "article_limit", "shards", "partition_strategy"]);
  for (let index = 0; index < args.length; index++) {
    const token = args[index]!;
    if (token === "--cli" || token === "--serve") {
      if (mode !== undefined) throw new PlanError("INVALID_REQUEST", "choose exactly one mode", "mode");
      mode = token === "--cli" ? "cli" : "serve";
      continue;
    }
    const [flag, inline] = token.split(/=(.*)/s);
    const field = flag!.replace(/^--/, "").replaceAll("-", "_");
    if (!flag!.startsWith("--") || !fields.has(field)) {
      throw new PlanError("INVALID_REQUEST", "unknown CLI control", field);
    }
    if (Object.hasOwn(raw, field)) throw new PlanError("INVALID_REQUEST", "repeated CLI control", field);
    const next = args[index + 1];
    const value = inline ?? (next !== undefined && !next.startsWith("--") ? args[++index]! : "");
    raw[field] = value.trim() === "" ? undefined
      : field === "partition_strategy" ? value : Number(value);
  }
  if (mode === undefined) throw new PlanError("INVALID_REQUEST", "choose --cli or --serve", "mode");
  if (mode === "serve" && Object.keys(raw).length) {
    throw new PlanError("INVALID_REQUEST", "serve mode accepts controls in each API request only", "mode");
  }
  return { mode, request: PlanRequestSchema.parse(raw) };
}

export function describePlanError(error: unknown, root?: string) {
  const message = (value: string) => root === undefined ? value : value.replaceAll(root, ".").replaceAll("\\", "/");
  if (error instanceof z.ZodError) return {
    code: "INVALID_INPUT", issues: error.issues.flatMap(issue =>
      (issue.code === "unrecognized_keys" ? issue.keys.map(key => [...issue.path, key]) : [issue.path])
        .map(path => ({ field: path.map(String).join(".") || "body", message: message(issue.message) }))),
  };
  if (error instanceof PlanError) return {
    code: error.code, issues: [{ field: error.field, message: message(error.message) }],
  };
  return {
    code: "PLAN_FAILED",
    issues: [{ field: error instanceof Error && "path" in error && typeof error.path === "string" && root !== undefined
      ? relative(root, error.path).replaceAll("\\", "/") : null,
    message: error instanceof Error ? message(error.message) : "Unknown planner failure" }],
  };
}
