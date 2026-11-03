/** Which committed configuration starts the summarizer HTTP entry point? */
import { loadEventSources } from "@idhazh/common-contracts/load-event-sources";
import { createHttpServer } from "./api/serve-http-api.js";
import { loadEnvConfig } from "./config/load-env-config.js";

const env = loadEnvConfig();
const sources = await loadEventSources(new URL("../../../config/typescript-event-sources.json", import.meta.url));
const app = createHttpServer({
  port: env.PORT, runtime: env.modelRuntime, eventSource: sources.summarizer,
});
app.start();