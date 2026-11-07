/** Which fixed HTTP suffixes do feed-planner and data-delivery handlers share? */
export const PLANNER_API_PATHS = {
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
} as const;

export const DELIVERY_API_PATHS = {
  health: "/get-data-delivery-health",
  persistData: "/persist-data",
} as const;
