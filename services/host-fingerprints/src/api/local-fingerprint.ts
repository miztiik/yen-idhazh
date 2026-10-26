/** How does a caller obtain one persisted fingerprint through its own loopback listener? */
import { FingerprintRequestSchema } from "../config";
import type { SelectedSettings, ServiceConfig } from "../config";
import type { PersistenceOptions } from "../persist-fingerprint";
import { FingerprintHealthSchema, FingerprintResponseSchema } from "./fingerprint-response";
import { FINGERPRINT_PATH, HEALTH_PATH, serveFingerprints } from "./server";

async function readResponse(response: Response, limit: number): Promise<unknown> {
  if (response.status !== 200 || response.headers.get("cache-control") !== "no-store") {
    await response.body?.cancel();
    throw new Error(`Fingerprint HTTP request failed (${response.status})`);
  }
  const reader = response.body?.getReader();
  if (reader === undefined) throw new Error("Fingerprint HTTP response has no body");
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const part = await reader.read();
      if (part.done) break;
      size += part.value.length;
      if (size > limit) {
        await reader.cancel();
        throw new Error("Fingerprint HTTP response exceeds max_input_bytes");
      }
      chunks.push(part.value);
    }
  } finally { reader.releaseLock(); }
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

export async function captureLocalFingerprint(
  input: unknown, config: ServiceConfig, settings: SelectedSettings, options: PersistenceOptions,
) {
  const request = FingerprintRequestSchema.parse(input);
  if (config.listen_host !== "127.0.0.1" && config.listen_host !== "::1") {
    throw new Error("Fingerprint collection requires a loopback listener on this runner");
  }
  const server = serveFingerprints(config, settings, options);
  try {
    const health = FingerprintHealthSchema.parse(await readResponse(
      await fetch(new URL(HEALTH_PATH, server.url), { redirect: "error" }), config.max_input_bytes,
    ));
    const enabled = settings.observability.host_telemetry_enabled && settings.observability.host_fingerprint;
    if (health.enabled !== enabled) throw new Error("Fingerprint health differs from the selected instrument controls");
    const response = FingerprintResponseSchema.parse(await readResponse(
      await fetch(new URL(FINGERPRINT_PATH, server.url), {
        method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(request),
        redirect: "error", timeout: false,
      }), config.max_input_bytes,
    ));
    if ((response.status === "written") !== enabled) throw new Error("Fingerprint response differs from the selected instrument controls");
    return response;
  } finally { await server.stop(true); }
}
