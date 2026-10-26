/** Which versioned host endpoint handles this request without hidden writes? */
import type { ServiceConfig, SelectedSettings } from "../config";
import type { PersistenceOptions } from "../persist-fingerprint";
import { postFingerprint } from "./routes/fingerprint.route";
import { FingerprintHealthSchema } from "./fingerprint-response";

// Calendar-versioned routes identify the API protocol, not operator controls.
export const FINGERPRINT_PATH = "/api/2026-10-20/fingerprint";
export const HEALTH_PATH = "/api/2026-10-20/health";
export function createFingerprintHandler(config: ServiceConfig, settings: SelectedSettings, options: PersistenceOptions) {
  return async (request: Request): Promise<Response> => {
    const path = new URL(request.url).pathname;
    if (path === HEALTH_PATH && request.method === "GET") {
      return Response.json(FingerprintHealthSchema.parse({
        status: "ok", enabled: settings.observability.host_telemetry_enabled && settings.observability.host_fingerprint,
      }), { headers: { "Cache-Control": "no-store" } });
    }
    if (path !== FINGERPRINT_PATH && path !== HEALTH_PATH) return Response.json({ error: "Not found" }, { status: 404 });
    if (path === FINGERPRINT_PATH && request.method === "POST") return postFingerprint(request, config, settings, options);
    return Response.json({ error: "Method not allowed" }, { status: 405, headers: { Allow: path === HEALTH_PATH ? "GET" : "POST" } });
  };
}
export function serveFingerprints(config: ServiceConfig, settings: SelectedSettings, options: PersistenceOptions) {
  return Bun.serve({
    hostname: config.listen_host, port: config.listen_port, maxRequestBodySize: config.max_input_bytes,
    fetch: createFingerprintHandler(config, settings, options),
    error(error) {
      console.error(JSON.stringify({ event: "host_fingerprint_failed", error: error.name }));
      return Response.json({ error: "Host fingerprint persistence failed" }, { status: 500 });
    },
  });
}
