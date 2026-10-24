import { EnvironmentVariablesSchema, type EnvironmentVariables } from "../schemas/export-all-schemas.js";
import { loadModelRuntime, type ModelRuntime } from "./load-model-runtime.js";

type RuntimeEnvironment = EnvironmentVariables & { modelRuntime: ModelRuntime };
let cachedEnv: RuntimeEnvironment | null = null;

export function loadEnvConfig(): RuntimeEnvironment {
  if (cachedEnv) {
    return cachedEnv;
  }

  const result = EnvironmentVariablesSchema.safeParse(process.env);
  if (!result.success) {
    console.error("❌ Environment configuration validation failed:");
    console.error(JSON.stringify(result.error.format(), null, 2));
    throw new Error("Invalid environment configuration.");
  }

  cachedEnv = { ...result.data, modelRuntime: loadModelRuntime(result.data.CONFIG_ROOT) };
  return cachedEnv;
}