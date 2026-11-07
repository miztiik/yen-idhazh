/** Do the shared feed HTTP suffixes preserve the declared operation names and independent prefix? */
import { expect, test } from "bun:test";
import { DELIVERY_API_PATHS, PLANNER_API_PATHS, PLANNER_API_PREFIX, PLANNER_PROTOCOL_VERSION } from "../src/index";

test("planner and delivery declare suffixes beneath the current fixed protocol date", () => {
  expect(PLANNER_PROTOCOL_VERSION).toBe("2026-11-07");
  expect(PLANNER_API_PREFIX).toBe("/api/2026-11-07");
  expect(PLANNER_API_PATHS).toEqual({
    health: "/get-feed-planner-health",
    plan: "/plan-feed-ingestion",
    fetch: "/fetch-document",
    parse: "/parse-document",
    startCollection: "/start-feed-collection",
    checkCollection: "/check-feed-collection",
    completeCollection: "/complete-feed-collection",
    cancelCollection: "/cancel-feed-collection",
    finalizeCollection: "/finalize-feed-collection",
    releaseCollection: "/release-feed-collection",
    updateFeedHealth: "/update-feed-health",
    selectArticles: "/select-articles",
    partitionArticles: "/partition-articles",
    persistSelectedArticles: "/persist-selected-articles",
  });
  expect(DELIVERY_API_PATHS).toEqual({
    health: "/get-data-delivery-health",
    persistData: "/persist-data",
  });
  const suffixes = [...Object.values(PLANNER_API_PATHS), ...Object.values(DELIVERY_API_PATHS)];
  expect(new Set(suffixes).size).toBe(suffixes.length);
  for (const suffix of suffixes) {
    expect(suffix).toMatch(/^\/[a-z]+(?:-[a-z]+)+$/);
    expect(`${PLANNER_API_PREFIX}${suffix}`).toBe(`/api/${PLANNER_PROTOCOL_VERSION}${suffix}`);
  }
});
