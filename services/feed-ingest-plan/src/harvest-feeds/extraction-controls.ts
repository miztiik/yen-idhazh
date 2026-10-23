/** Which existing extraction settings govern measured article quality? */
import { z } from "zod";
import { NonEmptySchema } from "@idhazh/common-contracts";

export const ExtractionControlsSchema = z.object({
  max_body_bytes: z.int().min(1024), max_retries: z.int().nonnegative(),
  backoff_initial_seconds: z.number().finite().nonnegative(),
  backoff_multiplier: z.number().finite().min(1),
  paywall_markers: z.array(NonEmptySchema).min(1),
  truncation_cap_tokens: z.int().min(256), min_source_words: z.int().min(1),
  prose_sentence_min: z.int().min(1), prose_sentence_words_min: z.int().min(1),
  prose_line_count_min: z.int().min(1), prose_line_ratio_min: z.number().finite().min(0).max(1),
  boilerplate_ratio_max: z.number().finite().gt(0).max(1),
  corroboration_ratio_max: z.number().finite().gt(1), corroboration_min_words: z.int().min(1),
  reject_not_prose: z.boolean(), reject_too_short: z.boolean(),
  reject_boilerplate: z.boolean(), reject_contaminated: z.boolean(),
});
export type ExtractionControls = z.infer<typeof ExtractionControlsSchema>;
