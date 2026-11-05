/** Run one native listener until its private parent pipe closes, with bounded awaited shutdown. */
import { createInterface } from "node:readline";
import type { HttpChildFailure, HttpChildFailurePolicy, HttpChildKind } from "./http-child-failure";

type HttpServer = { stop(force?: boolean): Promise<void> };

export async function runHttpChild<Failure extends HttpChildFailure>(
  kind: HttpChildKind,
  initialFailure: HttpChildFailurePolicy<Failure>,
  prepare: (message: unknown) => {
    shutdownTimeoutMs: number;
    failure?: HttpChildFailurePolicy<Failure>;
    start: (signal: AbortSignal) => Promise<{ server: HttpServer; ready: object }>;
  },
) {
  const lines = createInterface({ input: process.stdin, crlfDelay: Infinity });
  const cancellation = new AbortController();
  let server: HttpServer | undefined;
  let closing: Promise<void> | undefined;
  let shutdownMs: number | undefined;
  let forceTimer: ReturnType<typeof setTimeout> | undefined;
  let closed = false;
  let failure = initialFailure;
  let original: Failure | undefined;
  const stop = () => {
    closed = true;
    cancellation.abort(new Error("HTTP child supervisor closed"));
    if (shutdownMs !== undefined) forceTimer ??= setTimeout(() => {
      console.error(JSON.stringify({ event: `${kind.toLowerCase()}_shutdown_forced` }));
      void server?.stop(true).catch(error => console.error(JSON.stringify({
        event: `${kind.toLowerCase()}_forced_close_failed`, ...failure.describe(error),
      })));
      process.exit(2);
    }, shutdownMs);
    const current = server;
    if (current === undefined) { lines.close(); return; }
    closing ??= (async () => {
      try { await current.stop(); }
      finally { lines.close(); }
    })();
    void closing.catch(() => {});
  };
  process.on("SIGINT", stop);
  process.on("SIGTERM", stop);
  lines.once("close", stop);
  try {
    const line = await new Promise<string>((resolveLine, reject) => {
      lines.once("line", resolveLine);
      lines.once("close", () => reject(failure.create(`${kind}_STARTUP_CLOSED`, "Startup pipe closed before startup")));
    });
    const message: unknown = JSON.parse(line);
    const prepared = prepare(message);
    failure = prepared.failure ?? failure;
    shutdownMs = prepared.shutdownTimeoutMs;
    if (closed) throw failure.create(`${kind}_STARTUP_CLOSED`, "Supervisor left before listener startup");
    const started = await prepared.start(cancellation.signal);
    server = started.server;
    if (closed) {
      stop();
      throw failure.create(`${kind}_STARTUP_CLOSED`, "Supervisor left before listener startup");
    }
    console.log(JSON.stringify(started.ready));
    await new Promise<void>(resolveClosed => {
      if (closed) resolveClosed();
      else lines.once("close", resolveClosed);
    });
    await closing;
  } catch (error) {
    const captured = failure.startup(error, kind);
    original = captured.error;
    console.log(JSON.stringify(captured.packet));
    throw original;
  } finally {
    try {
      const close = () => { stop(); return closing; };
      if (original !== undefined) throw await failure.retainCleanup(original, close);
      await close();
    } finally {
      clearTimeout(forceTimer);
      lines.close();
      process.off("SIGINT", stop);
      process.off("SIGTERM", stop);
    }
  }
}
