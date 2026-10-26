/** Project body-free feed and article activity into sparse progress callbacks. */
export type ProgressEventType =
  | "FEED_FETCH_STARTED" | "FEED_FETCH_COMPLETED"
  | "ARTICLE_HARVEST_STARTED" | "ARTICLE_HARVEST_COMPLETED"
  | "ARTICLE_EXTRACTION_WARNING";
export type ProgressDetails = {
  source_id?: string; candidate_id?: string; output_count?: number; diagnostics?: unknown;
};
export type ProgressRecord = {
  eventType: ProgressEventType; source_id: string | null; output_count: number | null;
};
export function createProgressLogger(
  _correlationId: string, write?: (record: ProgressRecord) => void,
) {
  return (eventType: ProgressEventType, details: ProgressDetails = {}) => {
    write?.({ eventType, source_id: details.source_id ?? null, output_count: details.output_count ?? null });
  };
}
