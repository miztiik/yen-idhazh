/** Which source, base prompt and matching legacy controls may one full-analysis request supply? */
import { z } from "zod";

const sourceFields = {
  url: z.string().trim().optional().default(""),
  input_text: z.string().trim().optional().default(""),
};
const hasSource = (data: { url: string; input_text: string }) => Boolean(data.url || data.input_text);
const sourceRefusal = {
  message: "Execution rejected: Either 'url' or 'input_text' must be provided.",
  path: ["input_text"],
};
export const SourceInputSchema = z.object(sourceFields).refine(hasSource, sourceRefusal);
export type SourceInput = z.input<typeof SourceInputSchema>;

export const SummarizeRequestSchema = z
  .object({
    ...sourceFields,
    system_prompt: z.string().trim().min(1, "System prompt is required"),
    server_url: z.string().url("server_url must be a valid URL").optional(),
    model_name: z.string().min(1, "model_name cannot be empty").optional(),
  })
  .refine(hasSource, sourceRefusal);

export type SummarizeRequest = z.infer<typeof SummarizeRequestSchema>;