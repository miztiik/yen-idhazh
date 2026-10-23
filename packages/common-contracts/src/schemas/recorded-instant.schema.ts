/** Which saved UTC clock spellings retain their original second or millisecond precision? */
import { z } from "zod";
import { RECORDED_INSTANT_PATTERN, validRecordedInstant } from "../observation-order";

export const RecordedInstantSchema = z.string().regex(RECORDED_INSTANT_PATTERN)
  .refine(validRecordedInstant, "must be a valid UTC second or millisecond instant");
