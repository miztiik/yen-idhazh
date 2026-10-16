// services/summarizer/src/index.ts
import { createHttpServer } from "./api/serve-http-api.js";
import { loadEnvConfig } from "./config/load-env-config.js";

const env = loadEnvConfig();
const app = createHttpServer(env.PORT);
app.start();

export * from "./schemas/export-all-schemas.js";
export * from "./pipeline/orchestrate-pipeline.service.js";
export * from "./services/dispatch-event.service.js";
export * from "./api/serve-http-api.js";