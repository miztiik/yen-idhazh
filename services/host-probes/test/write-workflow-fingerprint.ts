/** Capture named runner openings through the native host route without external requests. */
import { z } from "zod";
import { createFingerprintHandler, FINGERPRINT_PATH } from "@idhazh/host-fingerprints/api";
import { FingerprintRequestSchema, loadConfig, loadSettings } from "@idhazh/host-fingerprints/config";

const captures = z.array(z.strictObject({
  state: z.string(), request: FingerprintRequestSchema,
})).parse(JSON.parse(await Bun.stdin.text()));
const configRoot = new URL("../../../config/", import.meta.url);
const config = await loadConfig(new URL("host-fingerprints.json", configRoot));
const settings = await loadSettings(new URL("idhazh.json", configRoot));
settings.observability.host_fingerprint_placement_enabled = false;
settings.observability.host_fingerprint_bandwidth_jobs = [];
for (const { state, request } of captures) {
  const handler = createFingerprintHandler(config, settings, {
    outputRoot: state, registryPath: new URL("ledgers.json", configRoot),
  });
  const reply = await handler(new Request(`http://localhost${FINGERPRINT_PATH}`, {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(request),
  }));
  if (!reply.ok) throw new Error(`${reply.status}: ${await reply.text()}`);
  console.log(await reply.text());
}
