import { EnvironmentVariablesSchema, type EnvironmentVariables } from "../schemas/export-all-schemas.js";

let cachedEnv: EnvironmentVariables | null = null;

export function loadEnvConfig(): EnvironmentVariables {
  if (cachedEnv) {
    return cachedEnv;
  }

  const result = EnvironmentVariablesSchema.safeParse(process.env);
  if (!result.success) {
    console.error("❌ Environment configuration validation failed:");
    console.error(JSON.stringify(result.error.format(), null, 2));
    throw new Error("Invalid environment configuration.");
  }

  cachedEnv = result.data;
  return cachedEnv;
}