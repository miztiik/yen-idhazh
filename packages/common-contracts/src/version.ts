/** Which schema and package stamps do current readers and writers use? */
export const CONTRACT_VERSION = "2026-10-20" as const;
export const PACKAGE_VERSION = "2026.10.20" as const;
export const EXTRACTION_QUALITY_VERSION = "2026-10-23" as const;
export const PUBLISHER_IDENTITY_VERSION = "2026-10-24T20:04" as const;
export const DISCOVERED_ARTICLE_VERSION = "2026-11-04" as const;
export const SELECTED_ARTICLE_VERSION = "2026-11-04" as const;
export const PLAN_RUN_VERSION = "2026-11-02" as const;
export const PLANNER_ENVELOPE_VERSION = "2026-10-31" as const;
export const FEED_HEALTH_STATE_VERSION = "2026-11-03" as const;
// The dated route identifies the current planner request and response protocol.
export const PLANNER_PROTOCOL_VERSION = "2026-11-02" as const;
export const PLANNER_API_PREFIX = `/api/${PLANNER_PROTOCOL_VERSION}` as const;
export const FEED_INGEST_CANDIDATE_VERSION = "2026-11-04" as const;
export const PARSED_FEED_BATCH_VERSION = "2026-11-03" as const;
export const SELECTED_FEED_BATCH_VERSION = "2026-11-03" as const;
export const FEED_OUTCOME_PAYLOAD_VERSION = "2026-11-02" as const;
export const FEED_PROBE_VERSION = "2026-11-02" as const;
export const FEED_INGEST_EVENT_VERSION = "2026-11-03" as const;
export const FEED_INGEST_CONFIG_VERSION = "2026-11-04" as const;
export const SCREENED_ARTICLE_VERSION = "2026-11-02" as const;
