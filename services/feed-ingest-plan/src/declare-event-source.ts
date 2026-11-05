/** Identify the planner's logical producer independently of deployment or source paths. */
export const PLANNER_EVENT_SOURCE: string = "/services/feed-ingest-plan";

// Delivery retains its published producer namespace independently of shared hosting.
export const DELIVERY_EVENT_SOURCE = "/services/typescript-api";
