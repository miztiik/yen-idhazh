/** Verify native source streams and fingerprints against generated loopback HTTP responses. */
import { expect, test } from "bun:test";
import { fork } from "node:child_process";
import { join } from "node:path";
import { once } from "node:events";
import { createConnection } from "node:net";
import { createImpitTransport } from "../src/harvest-feeds/impit-transport";
import { BodyLimitError, ResponseReadError } from "../src/harvest-feeds/transport";
import { TimeoutError } from "impit";
import { inputs } from "./harvest-recordings";

test("native profiles decode compressed bodies and retain status at cutoff and cancellation", async () => {
  const configured = await Bun.file(new URL("../../../config/feed-ingest-plan.json", import.meta.url)).json();
  const loaded = await inputs(undefined, { harvest: { fetch_timeout_ms: configured.harvest.fetch_timeout_ms } });
  const payload = Buffer.from("generated response ".repeat(300));
  let followed = 0;
  const agents: string[] = [];
  const cancellations = new Map<string, () => void>();
  const arrivals = new Map<string, () => void>();
  const closed = new Map<string, number>();
  const continued = new Set<string>();
  const retryAfter = "1".repeat(300);
  const server = fork(join(import.meta.dir, "impit-loopback-source.cjs"), [String(loaded.config.harvest.fetch_timeout_ms)], {
    execPath: "node", stdio: ["ignore", "ignore", "inherit", "ipc"],
  });
  const port = await new Promise<number>((resolve, reject) => {
    server.once("error", reject);
    server.once("exit", code => reject(new Error(`Generated source exited before readiness: ${code}`)));
    server.on("message", (message: unknown) => {
      if (typeof message !== "object" || message === null) throw new Error("Invalid generated-source event");
      if ("port" in message && typeof message.port === "number") resolve(message.port);
      else if ("agent" in message && typeof message.agent === "string") agents.push(message.agent);
      else if ("followed" in message && message.followed === true) followed++;
      else if ("received" in message && typeof message.received === "string") arrivals.get(message.received)?.();
      else if ("continued" in message && typeof message.continued === "string") continued.add(message.continued);
      else if ("closed" in message && typeof message.closed === "string") {
        closed.set(message.closed, performance.now());
        cancellations.get(message.closed)?.();
      } else throw new Error("Unknown generated-source event");
    });
  });
  const transport = createImpitTransport();
  const base = { profile: loaded.config.harvest.request_headers.primary,
    diagnostics: loaded.config.harvest.response_diagnostics,
    signal: new AbortController().signal, max_body_bytes: payload.byteLength,
    timeout_ms: loaded.config.harvest.fetch_timeout_ms };
  const target = (path: string) => new URL(`http://127.0.0.1:${port}/${path}`);
  async function cancelled(path: string) {
    if (closed.has(path)) return;
    const cancellation = new Promise<void>(resolve => cancellations.set(path, resolve));
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      await Promise.race([cancellation, new Promise<never>((_, reject) => {
        timer = setTimeout(() => reject(new Error(`Native cancellation left the ${path} response open`)), 1000);
      })]);
    } finally { clearTimeout(timer); cancellations.delete(path); }
  }
  try {
    const reference = createConnection({ host: "127.0.0.1", port });
    try {
      await once(reference, "connect");
      const received = once(reference, "data");
      reference.write("GET /reference HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n");
      await received;
    } finally { reference.destroy(); }
    await cancelled("reference");
    for (const encoding of ["gzip", "br", "deflate"]) {
      const result = await transport.request({ ...base, url: target(encoding) });
      expect(result.body).toBe(payload.toString());
      expect(result.status).toBe(403);
      expect(result.evidence).toMatchObject({
        decoded_bytes: payload.byteLength, content_type: "text/html", request_profile: "firefox",
        selected_headers: { "retry-after": retryAfter.slice(0, base.diagnostics.max_header_value_chars) },
        headers_truncated: ["retry-after"],
      });
    }
    try {
      await transport.request({ ...base, url: target("gzip"), max_body_bytes: 100 });
      throw new Error("oversized decoded response must fail");
    } catch (error) {
      expect(error).toBeInstanceOf(ResponseReadError);
      if (!(error instanceof ResponseReadError)) throw error;
      expect(error.http_status).toBe(403);
      expect(error.response_evidence.decoded_bytes).toBeGreaterThan(100);
      expect(error.cause).toBeInstanceOf(BodyLimitError);
    }
    const redirect = await transport.request({ ...base, url: target("redirect") });
    expect(redirect.status).toBe(302);
    expect(redirect.location).toBe("/followed");
    expect(followed).toBe(0);
    try {
      await transport.request({ ...base, url: target("cutoff"), max_body_bytes: 100 });
      throw new Error("An open oversized response must stop at the decoded cutoff");
    } catch (error) {
      expect(error).toBeInstanceOf(ResponseReadError);
      if (!(error instanceof ResponseReadError)) throw error;
      expect(error.http_status).toBe(403);
      expect(error.response_evidence.decoded_bytes).toBeGreaterThan(100);
      expect(error.cause).toBeInstanceOf(BodyLimitError);
    }
    await cancelled("cutoff");
    const controller = new AbortController();
    const stalled = transport.request({ ...base, max_body_bytes: 32768, url: target("stalled"), signal: controller.signal });
    const timer = setTimeout(() => controller.abort(), 300);
    try {
      await expect(stalled).rejects.toMatchObject({ http_status: 403,
        response_evidence: { content_type: "text/html", decoded_bytes: 16384 } });
    } finally { clearTimeout(timer); }
    await cancelled("stalled");
    if (loaded.config.harvest.request_headers.secondary === null) throw new Error("test needs secondary profile");
    await transport.request({ ...base, profile: loaded.config.harvest.request_headers.secondary, url: target("redirect") });
    expect(agents[1]).toContain("Firefox/");
    expect(agents.at(-1)).toContain("Chrome/");
    expect(agents.every(agent => !agent.includes("compatible;"))).toBe(true);
    for (const path of ["no-headers", "late-headers"]) {
      const received = new Promise<void>(resolve => arrivals.set(path, resolve));
      const early = new AbortController();
      let settled = false;
      const started = performance.now();
      const request = transport.request({ ...base, url: target(path), signal: early.signal, timeout_ms: 500 });
      void request.then(() => { settled = true; }, () => { settled = true; });
      await received;
      early.abort();
      await Promise.resolve();
      expect(settled).toBe(false);
      if (path === "late-headers") {
        await expect(request).rejects.toMatchObject({
          http_status: 403, response_evidence: { content_type: "text/html", decoded_bytes: null },
        });
      } else {
        await expect(request).rejects.toBeInstanceOf(TimeoutError);
        expect(performance.now() - started).toBeGreaterThanOrEqual(250);
      }
      await cancelled(path);
      arrivals.delete(path);
    }
    closed.delete("no-headers");
    await expect(transport.request({ ...base, url: target("no-headers"), timeout_ms: 200 }))
      .rejects.toBeInstanceOf(TimeoutError);
    await cancelled("no-headers");
    const started = performance.now();
    try {
      await transport.request({ ...base, url: target("body-timeout"), max_body_bytes: 32768 });
      throw new Error("An unfinished body must fail at the native request deadline");
    } catch (error) {
      expect(error).toBeInstanceOf(ResponseReadError);
      if (!(error instanceof ResponseReadError)) throw error;
      const primary = error.cause instanceof AggregateError ? error.cause.cause : error.cause;
      expect(primary).toBeInstanceOf(TimeoutError);
      expect(error.http_status).toBe(403);
      expect(error.response_evidence.decoded_bytes).toBe(16384);
    }
    const rejectedAfterMs = performance.now() - started;
    try { await cancelled("body-timeout"); }
    catch (oracleError) {
      const closedAt = closed.get("body-timeout");
      console.info(JSON.stringify({ control: "body-timeout", native_timeout_ms: base.timeout_ms,
        read_rejected_after_ms: rejectedAfterMs, source_wrote_after_timeout: continued.has("body-timeout"),
        source_closed_after_ms: closedAt === undefined ? null : closedAt - started,
        observed_until_ms: performance.now() - started }));
      throw oracleError;
    }
  } finally {
    const exited = once(server, "exit");
    server.send("stop");
    expect((await exited)[0]).toBe(0);
  }
}, 15000);
