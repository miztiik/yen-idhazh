/** Do declared listeners and saved identities stay isolated without inventing old observations? */
import { expect, test } from "bun:test";
import { z } from "zod";
import { ApiReadySchema } from "../src/api-startup";
import type { ApiReady } from "../src/api-startup";
import { HonoServerConfigSchema, HONO_SETTINGS_VERSION, selectHonoSettings } from "../src/load-settings";
import { createServerEvidenceSchema, serverLogFilename } from "../src/server-evidence";
import type { CurrentServerEvidence } from "../src/server-evidence";

const configuration = HonoServerConfigSchema.parse({
  version: HONO_SETTINGS_VERSION,
  listeners: {
    planning: { hostname: "127.0.0.1", port: 8787 },
    machine: { hostname: "127.0.0.1", port: 8788 },
    delivery: { hostname: "127.0.0.1", port: 8789 },
  },
  idle_timeout_seconds: 30,
  supervision: { readiness_timeout_ms: 30000, shutdown_timeout_ms: 10000, forced_exit_timeout_ms: 5000 },
});

test("changing one configured listener changes only that server's selected address", () => {
  const changed = structuredClone(configuration);
  changed.listeners.machine.port = 18000;
  expect(selectHonoSettings(changed, "machine").port).toBe(18000);
  expect(selectHonoSettings(changed, "planning")).toEqual(selectHonoSettings(configuration, "planning"));
  expect(selectHonoSettings(changed, "delivery")).toEqual(selectHonoSettings(configuration, "delivery"));
});

test("collisions and incomplete or legacy listener maps fail before process startup", () => {
  const collided = structuredClone(configuration);
  collided.listeners.machine = { ...collided.listeners.planning };
  const invalid = HonoServerConfigSchema.safeParse(collided);
  expect(invalid.success).toBe(false);
  if (invalid.success) throw new Error("A shared listener cannot identify independent API servers");
  expect(invalid.error.issues.map(issue => issue.path)).toContainEqual(["listeners", "machine", "port"]);
  const { machine, ...missing } = configuration.listeners;
  expect(HonoServerConfigSchema.safeParse({ ...configuration, listeners: missing }).success).toBe(false);
  expect(HonoServerConfigSchema.safeParse({
    ...configuration, listeners: { ...configuration.listeners, unregistered: machine },
  }).success).toBe(false);
  expect(HonoServerConfigSchema.safeParse({
    hostname: machine.hostname, port: machine.port,
    idle_timeout_seconds: configuration.idle_timeout_seconds, supervision: configuration.supervision,
  }).success).toBe(false);
});

test("readiness identifies one selected native module rather than a combined or foreign application", () => {
  const identity: ApiReady = {
    event: "typescript_api_ready", nonce: crypto.randomUUID(), pid: 1234, port: 8787,
    group: "planning", modules: ["planning"], enabled: true,
  };
  expect(ApiReadySchema.parse(identity)).toEqual(identity);
  for (const modules of [[], ["machine"], ["planning", "machine"], ["planning", "planning"]]) {
    expect(ApiReadySchema.safeParse({ ...identity, modules }).success).toBe(false);
  }
});

test("legacy evidence preserves its date and absent identity while current records require genuine readiness", () => {
  const schema = createServerEvidenceSchema(z.never());
  const observed: Omit<CurrentServerEvidence<never>,
    "version" | "log_filename" | "listener" | "identity" | "reported_profiles"> = {
    server_name: "hono-server", group: "planning", run_id: "700", attempt: 3,
    started_at: "2026-11-04T00:00:00Z", pid: null, startup: "not_started", startup_ms: null,
    shutdown: "not_started", exit_code: null, log_available: false, error_code: null, cleanup_error_code: null,
  };
  const legacy = schema.parse({
    ...observed, version: "2026-11-04", log_filename: "hono-server_2026_11_04_700_3.log",
  });
  expect(legacy.version).toBe("2026-11-04");
  expect(legacy.reported_profiles).toEqual([]);
  expect(legacy).not.toHaveProperty("identity");
  expect(legacy).not.toHaveProperty("listener");
  const current: CurrentServerEvidence<never> = {
    ...observed, version: "2026-11-07", log_filename: serverLogFilename("planning", observed),
    listener: configuration.listeners.planning, identity: null, reported_profiles: [],
  };
  expect(schema.parse(current)).toEqual(current);
  expect(schema.safeParse({ ...current, startup: "ready" }).success).toBe(false);
  expect(schema.safeParse({ ...current, version: "2026-11-06" }).success).toBe(false);
  expect(schema.safeParse({ ...current, log_filename: legacy.log_filename }).success).toBe(false);
  expect(serverLogFilename("machine", observed)).not.toBe(current.log_filename);
});
