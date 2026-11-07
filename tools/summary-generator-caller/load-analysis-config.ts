/** Which committed preparation, capture and prompt settings belong to the caller? */
import { readFileSync } from "node:fs";
import path from "node:path";
import { z } from "zod";
import {
  generatorRepositoryRoot, GeneratorLoggingSchema, NativeBoundsSchema, PromptFileSchema,
  RelativeConfigPathSchema, readPromptFile,
} from "../../services/summary-generator/src/config/load-generator-config.js";
import { loadModelRuntime } from "../../services/summary-generator/src/config/load-model-runtime.js";
import { EnvironmentVariablesSchema } from "./contracts/analysis-environment.schema.js";

export const AnalysisConfigSchema = NativeBoundsSchema.extend({
  version: z.literal("2026-11-06"),
  max_input_words: z.number().int().positive(),
  base_prompt_file: PromptFileSchema,
  analysis_prompt_file: PromptFileSchema,
  body_read_timeout_ms: z.number().int().positive(),
  heartbeat_ms: z.number().int().positive(),
  extraction_timeout_ms: z.number().int().positive(),
  min_html_bytes: z.number().int().positive(),
  min_content_characters: z.number().int().positive(),
  api_startup_timeout_ms: z.number().int().positive(),
  api_poll_interval_ms: z.number().int().positive(),
  output_directory: RelativeConfigPathSchema,
  logging: GeneratorLoggingSchema,
}).strict();
export type AnalysisConfig = z.infer<typeof AnalysisConfigSchema>;
export type AnalysisSettings = { config: AnalysisConfig; analysisPrompt: string };

export function loadAnalysisConfig(configRoot = path.join(generatorRepositoryRoot, "config")) {
  return AnalysisConfigSchema.parse(JSON.parse(
    readFileSync(path.join(configRoot, "summary-generator/workflow.json"), "utf8"),
  ));
}
export function loadAnalysisSettings(configRoot = path.join(generatorRepositoryRoot, "config")): AnalysisSettings {
  const config = loadAnalysisConfig(configRoot);
  return { config, analysisPrompt: readPromptFile(configRoot, config.analysis_prompt_file) };
}
export function loadAnalysisPrompt(base: string, configRoot = path.join(generatorRepositoryRoot, "config")) {
  return `${base}\n\n${loadAnalysisSettings(configRoot).analysisPrompt}`;
}
export function loadEnvConfig(environment: NodeJS.ProcessEnv = process.env) {
  const env = EnvironmentVariablesSchema.parse(environment);
  const configRoot = env.CONFIG_ROOT ?? path.join(generatorRepositoryRoot, "config");
  const workflow = loadAnalysisConfig(configRoot);
  return {
    ...env,
    configRoot,
    PROMPT: env.PROMPT ?? readPromptFile(configRoot, workflow.base_prompt_file),
    analysisPrompt: readPromptFile(configRoot, workflow.analysis_prompt_file),
    workflow,
    modelRuntime: loadModelRuntime(configRoot),
  };
}
