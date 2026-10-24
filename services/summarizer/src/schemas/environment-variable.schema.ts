import { z } from "zod";

export const EnvironmentVariablesSchema = z.object({
  PORT: z.coerce.number().default(9932),
  CONFIG_ROOT: z.string().min(1).optional(),
  RUNNER_NAME: z.string().default("local-runner"),
  SHARD_ID: z.string().default("local-shard"),
  URL: z.string().optional().default(""),
  INPUT_TEXT: z.string().optional().default(""),
  PROMPT: z
    .string()
    .default(
      "You are an executive summarizer. Output ONLY the requested JSON. Do NOT output thinking tags or reasoning."
    ),
  GITHUB_STEP_SUMMARY: z.string().optional(),
});

export type EnvironmentVariables = z.infer<typeof EnvironmentVariablesSchema>;