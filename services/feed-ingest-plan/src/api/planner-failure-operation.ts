/** Identify a failed operation from a trusted planner route, never from source text. */
import { PLANNER_API_PATHS } from "@idhazh/common-contracts";
import type { PlannerFailureOperation } from "@idhazh/common-contracts";

const operations: Readonly<Record<string, PlannerFailureOperation>> = {
  [PLANNER_API_PATHS.plan]: "plan",
  [PLANNER_API_PATHS.fetch]: "fetch",
  [PLANNER_API_PATHS.parse]: "parse",
  [PLANNER_API_PATHS.startCollection]: "collection-start",
  [PLANNER_API_PATHS.checkCollection]: "collection-start",
  [PLANNER_API_PATHS.completeCollection]: "collection-complete",
  [PLANNER_API_PATHS.cancelCollection]: "collection-cancel",
  [PLANNER_API_PATHS.finalizeCollection]: "collection-finalize",
  [PLANNER_API_PATHS.releaseCollection]: "collection-release",
  [PLANNER_API_PATHS.selectArticles]: "select",
  [PLANNER_API_PATHS.partitionArticles]: "partition",
  [PLANNER_API_PATHS.persistSelectedArticles]: "persist",
  [PLANNER_API_PATHS.updateFeedHealth]: "feed-health-state",
};
export function plannerFailureOperation(route: string): PlannerFailureOperation {
  return operations[route] ?? "plan";
}
