/** Which prepared text and complete prompt override may one independent request supply? */
import { z } from "zod";

const nonblank = z.string().min(1).refine(value => value.trim().length > 0, "Text must not be blank.");
export const SummarizeRequestSchema = z.object({
  input_text: nonblank,
  system_prompt: nonblank.optional(),
}).strict();
export type SummarizeRequest = z.infer<typeof SummarizeRequestSchema>;
