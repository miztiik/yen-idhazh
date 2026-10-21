/** Which fingerprint operation did the operator request? */
import { parseArgs } from "node:util";
import { loadConfig, loadSettings } from "./config";
import { serveFingerprints } from "./api/server";
import { persistFingerprint } from "./persist-fingerprint";
export { collectFingerprint } from "./collect-fingerprint";
export { persistFingerprint } from "./persist-fingerprint";
export { createFingerprintHandler } from "./api/server";
export { loadConfig, loadSettings } from "./config";

async function main(): Promise<void> {
  const { values } = parseArgs({
    args: Bun.argv.slice(2), strict: true, allowPositionals: false,
    options: {
      serve: { type: "boolean" }, fingerprint: { type: "boolean" },
      context: { type: "string" }, "state-root": { type: "string" },
      config: { type: "string" }, settings: { type: "string" },
    },
  });
  if (!!values.serve === !!values.fingerprint || !values["state-root"] || (values.fingerprint && !values.context) || (values.serve && values.context)) {
    throw new Error("Usage: --fingerprint --context <file> --state-root <directory> | --serve --state-root <directory>; optional --config <file> --settings <selected idhazh.json>");
  }
  const config = await loadConfig(values.config);
  const settings = await loadSettings(values.settings);
  const options = { outputRoot: values["state-root"] };
  if (values.fingerprint) {
    console.log(JSON.stringify(await persistFingerprint(await Bun.file(values.context!).json(), config, settings, options)));
  } else {
    const server = serveFingerprints(config, settings, options);
    console.error(JSON.stringify({ listening: server.url.toString() }));
  }
}
if (import.meta.main) {
  try {
    await main();
  } catch (error: unknown) {
    console.error(JSON.stringify({ event: "host_fingerprint_failed", error: error instanceof Error ? error.name : "UnknownError",
      detail: error instanceof Error && (error.name === "ZodError" || error.message.startsWith("Usage:")) ? error.message : "Collection or persistence failed" }));
    process.exitCode = 1;
  }
}
