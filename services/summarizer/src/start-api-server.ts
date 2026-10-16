import { createHttpServer } from "./api/serve-http-api.js";
import { loadEnvConfig } from "./config/load-env-config.js";

const env = loadEnvConfig();
const app = createHttpServer(env.PORT);
app.start();