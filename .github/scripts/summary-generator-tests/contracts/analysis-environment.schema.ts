/** Which caller environment fields select input, prompts and private output without choosing a model? */
import { z } from "zod";

export const EnvironmentVariablesSchema = z.object({
  CONFIG_ROOT: z.string().min(1).optional(),
  URL: z.string().optional().default(""),
  INPUT_TEXT: z.string().optional().default(""),
  PROMPT: z.string().optional(),
  GITHUB_STEP_SUMMARY: z.string().optional(),
});

export type EnvironmentVariables = z.infer<typeof EnvironmentVariablesSchema>;