/** Which fingerprint operation did the operator request? */
import { parseArgs } from "node:util";
import { createRootContext } from "@idhazh/common-contracts";
import type { OperationMetadata } from "@idhazh/common-contracts";
import { loadConfig, loadSettings } from "./config";
import { serveFingerprints } from "./api/server";
import { persistFingerprint } from "./persist-fingerprint";
import { createFingerprintCompletionEvent, createFingerprintFailureEvent } from "./api/create-fingerprint-event";
export { collectFingerprint } from "./collect-fingerprint";
export { persistFingerprint } from "./persist-fingerprint";
export { createFingerprintHandler } from "./api/server";
export { loadConfig, loadSettings } from "./config";

async function main(context: OperationMetadata): Promise<void> {
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
    const result = await persistFingerprint(await Bun.file(values.context!).json(), config, settings, options);
    console.error(JSON.stringify(createFingerprintCompletionEvent({ context, status: result.status })));
    console.log(JSON.stringify(result));
  } else {
    const server = serveFingerprints(config, settings, options);
    console.error(JSON.stringify({ listening: server.url.toString() }));
  }
}
if (import.meta.main) {
  const context = createRootContext();
  try {
    await main(context);
  } catch {
    console.error(JSON.stringify(createFingerprintFailureEvent({ context })));
    process.exitCode = 1;
  }
}
