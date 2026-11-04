/** Project body-free feed and article activity into sparse progress callbacks. */
export type ProgressEventType =
  | "FEED_FETCH_STARTED" | "FEED_FETCH_COMPLETED"
  | "ARTICLE_HARVEST_STARTED" | "ARTICLE_HARVEST_COMPLETED"
  | "ARTICLE_EXTRACTION_WARNING";
export type ProgressDetails = {
  feed_id?: string; candidate_id?: string; output_count?: number; diagnostics?: unknown;
};
export type ProgressRecord = {
  eventType: ProgressEventType; feed_id: string | null; output_count: number | null;
};
