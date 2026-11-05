/** Which committed configuration starts the summarizer HTTP entry point? */
import { SUMMARIZER_EVENT_SOURCE } from "./declare-event-source.js";
import { createHttpServer } from "./api/serve-http-api.js";
import { loadEnvConfig } from "./config/load-env-config.js";

const env = loadEnvConfig();
const app = createHttpServer({
  port: env.PORT, runtime: env.modelRuntime, eventSource: SUMMARIZER_EVENT_SOURCE,
});
app.start();