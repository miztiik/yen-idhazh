/** Drive the real native profile route with two named recorded proc observations. */
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";
import { createMachineApp, loadMachineApiInputs } from "../src/api/create-machine-app";
import { START_ITEM_WINDOW_PATH } from "../src/api/server";

const root = Bun.argv[2];
if (root === undefined) throw new Error("Provide the recorded proc root");
const settled = z.record(z.string().regex(/^(stat|meminfo|loadavg|\d+\/(?:stat|status))$/), z.string())
  .parse(await Bun.file(join(root, "settled.json")).json());
const inputs = await loadMachineApiInputs(fileURLToPath(new URL("../../../", import.meta.url)), join(root, "state"));
const config = inputs.probes.config;
config.task_profile = { ...config.task_profile, enabled: true, memory_enabled: true, machine_memory_enabled: true };
const app = createMachineApp({
  ...inputs, probes: {
    config, context: { platform: "linux", procRoot: root }, diagnostics: { writeEvent: () => {} },
  },
});
const server = Bun.serve({
  port: 0, hostname: "127.0.0.1",
  async fetch(request) {
    const result = await app.fetch(request);
    if (result.ok && new URL(request.url).pathname === START_ITEM_WINDOW_PATH) {
      await Promise.all(Object.entries(settled).map(([name, text]) => Bun.write(join(root, name), text)));
    }
    return result;
  },
});
await Bun.write(join(root, "origin"), server.url.origin);
await Bun.stdin.text();
await app.close();
await server.stop(true);
