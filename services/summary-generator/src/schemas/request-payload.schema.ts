import { z } from "zod";

export const SummarizeRequestSchema = z
  .object({
    url: z.string().trim().optional().default(""),
    input_text: z.string().trim().optional().default(""),
    system_prompt: z.string().trim().min(1, "System prompt is required"),
    server_url: z.string().url("server_url must be a valid URL").optional(),
    model_name: z.string().min(1, "model_name cannot be empty").optional(),
  })
  .refine(
    (data) => Boolean((data.url && data.url.length > 0) || (data.input_text && data.input_text.length > 0)),
    {
      message: "Execution rejected: Either 'url' or 'input_text' must be provided.",
      path: ["input_text"],
    }
  );

export type SummarizeRequest = z.infer<typeof SummarizeRequestSchema>;