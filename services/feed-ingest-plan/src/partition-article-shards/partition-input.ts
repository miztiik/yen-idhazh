/** Which current selections have their exact original harvested content? */
import {
  EditorialSelectionRowSchema, FeedIngestCandidateSchema, FeedIngestDispatchSchema,
  FeedPartitionConfigSchema, PartitionAssignmentSchema,
} from "@idhazh/common-contracts";
import type { EditorialSelectionRow, FeedIngestCandidate, PartitionAssignment } from "@idhazh/common-contracts";
import type { z } from "zod";

export type PartitionRequest = Readonly<{
  strategy?: PartitionAssignment["strategy"];
  shards?: number;
}>;
export type ResolvedPartition = Readonly<{
  strategy: PartitionAssignment["strategy"];
  dispatch_count: number;
}>;
export type PartitionArticle = Readonly<{
  content: FeedIngestCandidate;
  selection: EditorialSelectionRow;
}>;

export function resolvePartitionRequest(
  settings: z.input<typeof FeedPartitionConfigSchema>, request: PartitionRequest = {},
): ResolvedPartition {
  const config = FeedPartitionConfigSchema.parse(settings);
  const strategy = PartitionAssignmentSchema.shape.strategy.parse(request.strategy ?? config.default_strategy);
  const count = request.shards ?? (strategy === "none" ? 1 : config.default_shards);
  if (!Number.isSafeInteger(count) || count < 1) throw new Error("shards must be a positive safe integer");
  if (strategy === "none") {
    if (count !== 1) throw new Error("none requires an omitted shard count or explicit one");
  } else if (count < config.min_shards || count > config.max_shards) {
    throw new Error(`shards must be within configured bounds ${config.min_shards}..${config.max_shards}`);
  }
  return { strategy, dispatch_count: count };
}

export function preparePartitionInput(
  selections: readonly EditorialSelectionRow[], candidates: readonly FeedIngestCandidate[],
  context: Readonly<{ date: string; run_id: string; correlation_id: string }>,
): PartitionArticle[] {
  const contentById = new Map<string, FeedIngestCandidate>();
  for (const value of candidates) {
    const candidate = FeedIngestCandidateSchema.parse(value);
    if (contentById.has(candidate.candidate_id)) throw new Error("Repeated candidate identity in partition input");
    contentById.set(candidate.candidate_id, candidate);
  }
  const identities = new Set<string>();
  const ranks = new Set<number>();
  const articles = selections.map(value => {
    const selection = EditorialSelectionRowSchema.parse(value);
    if (selection.date !== context.date || selection.correlation_id !== context.correlation_id) {
      throw new Error("Selection belongs to another planning context");
    }
    if (identities.has(selection.candidate_id) || ranks.has(selection.editorial_rank)) {
      throw new Error("Selected identities and editorial ranks must be distinct");
    }
    identities.add(selection.candidate_id);
    ranks.add(selection.editorial_rank);
    const content = contentById.get(selection.candidate_id);
    if (content === undefined) throw new Error(`Missing original content for selected candidate ${selection.candidate_id}`);
    const dispatch = FeedIngestDispatchSchema.parse({
      content, selection, partition: { strategy: "none", dispatch_count: 1, worker_assignment: 0 },
    });
    return { content: dispatch.content, selection: dispatch.selection };
  });
  return articles.sort((left, right) => left.selection.editorial_rank - right.selection.editorial_rank);
}
