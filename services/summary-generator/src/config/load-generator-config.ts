/** How are named generator settings and prompt bytes resolved without environment destinations? */
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";
import { SUMMARY_API_VERSION } from "../schemas/summary-result.schema.js";

export const generatorRepositoryRoot = fileURLToPath(new URL("../../../../", import.meta.url));
export const RelativeConfigPathSchema = z.string().regex(/^[A-Za-z0-9][A-Za-z0-9._/-]*$/)
  .refine(value => !value.split("/").includes(".."), "Parent traversal is not allowed.");
export const PromptFileSchema = RelativeConfigPathSchema.refine(
  value => value.startsWith("prompts/"), "Prompt files belong under prompts/.",
);
const positive = z.number().int().positive().max(Number.MAX_SAFE_INTEGER);
export const GeneratorLoggingSchema = z.object({
  level: z.enum(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
  max_event_bytes: positive,
}).strict();
export const NativeBoundsSchema = z.object({
  max_native_request_bytes: positive,
  max_native_response_bytes: positive,
}).strict();
export const GeneratorConfigSchema = NativeBoundsSchema.extend({
  version: z.literal(SUMMARY_API_VERSION),
  hostname: z.enum(["127.0.0.1", "::1"]),
  port: z.number().int().min(1).max(65535),
  prompt_file: PromptFileSchema,
  max_request_bytes: positive,
  body_read_timeout_ms: positive,
  logging: GeneratorLoggingSchema,
}).strict();
export type GeneratorConfig = z.infer<typeof GeneratorConfigSchema>;
export type NativeBounds = z.infer<typeof NativeBoundsSchema>;

export function readPromptFile(configRoot: string, name: string): string {
  const relative = PromptFileSchema.parse(name);
  const text = new TextDecoder("utf-8", { fatal: true }).decode(readFileSync(path.join(configRoot, relative)));
  if (!text.trim()) throw new Error("Configured prompt must not be blank.");
  return text;
}
export function readGeneratorConfig(configRoot = path.join(generatorRepositoryRoot, "config")): GeneratorConfig {
  return GeneratorConfigSchema.parse(JSON.parse(
    readFileSync(path.join(configRoot, "summary-generator/api.json"), "utf8"),
  ));
}
export function loadGeneratorConfig(configRoot = path.join(generatorRepositoryRoot, "config")) {
  const config = readGeneratorConfig(configRoot);
  return { config, systemPrompt: readPromptFile(configRoot, config.prompt_file) };
}
