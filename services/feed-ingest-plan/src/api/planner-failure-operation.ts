/** Identify a failed operation from a trusted planner route, never from source text. */
import type { PlannerFailureOperation } from "@idhazh/common-contracts";

const operations: Readonly<Record<string, PlannerFailureOperation>> = {
  plan: "plan", fetch: "fetch", parse: "parse",
  collections: "collection-start", "collections/exists": "collection-start",
  "collections/complete": "collection-complete", "collections/cancel": "collection-cancel",
  "collections/finalize": "collection-finalize", "collections/release": "collection-release",
  "select-articles": "select", "partition-articles": "partition",
  "persist-selected-articles": "persist", "feed-health-state": "feed-health-state",
};
export function plannerFailureOperation(route: string): PlannerFailureOperation {
  return operations[route] ?? "plan";
}
