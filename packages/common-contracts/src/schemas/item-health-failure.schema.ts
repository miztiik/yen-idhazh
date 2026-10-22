/** Which stable outcomes can be stored for an item-health row? */
import { z } from "zod";

export const ItemHealthFailureCodeSchema = z.enum([
  "not_attempted", "robots_denied", "robots_unreachable", "blocked_address",
  "http_client_error", "http_rate_limited", "http_server_error", "network_error",
  "no_text", "no_title", "too_short", "not_prose", "boilerplate", "contaminated",
  "paywalled", "unsupported_form", "model_unreachable", "model_refused",
  "model_timed_out", "context_exceeded", "output_truncated", "labels_truncated",
  "bad_shape", "length_out_of_range", "copied_source", "leaked_address",
  "shard_out_of_time", "unknown",
]);
export type ItemHealthFailureCode = z.infer<typeof ItemHealthFailureCodeSchema>;
