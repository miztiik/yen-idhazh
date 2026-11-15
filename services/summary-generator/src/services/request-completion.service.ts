/** How does one native completion consume bounded JSON within its complete deadline? */
import http from "node:http";
import https from "node:https";
import { performance } from "node:perf_hooks";
import { Readable } from "node:stream";
import { setImmediate as yieldRead } from "node:timers/promises";
import type { ModelRuntime } from "../config/load-model-runtime.js";
import type { NativeBounds } from "../config/load-generator-config.js";

export type CompletionFetch = (request: Request) => Promise<Response>;
export function isCompletionTimeout(error: unknown): boolean {
  return error instanceof Error && (error.name === "TimeoutError"
    || "code" in error && error.code === "ETIMEDOUT");
}

export async function sendHttpRequest(request: Request): Promise<Response> {
  request.signal?.throwIfAborted();
  const url = new URL(request.url);
  const bodyBuffer = request.body === null ? undefined : Buffer.from(await request.arrayBuffer());
  const transport = url.protocol === "https:" ? https : http;
  return new Promise<Response>((resolve, reject) => {
    let settled = false;
    const finish = <T>(complete: (value: T) => void, value: T) => {
      if (settled) return;
      settled = true;
      request.signal?.removeEventListener("abort", onAbort);
      complete(value);
    };
    const req = transport.request(url, {
      method: request.method,
      headers: Object.fromEntries(request.headers.entries()),
      agent: false,
    }, res => {
      if (request.redirect === "error" && res.statusCode !== undefined && res.statusCode >= 300 && res.statusCode < 400) {
        res.resume();
        finish(reject, new TypeError("Redirect mode is set to error."));
        return;
      }
      const headers = new Headers();
      for (const [name, value] of Object.entries(res.headers)) {
        if (Array.isArray(value)) {
          for (const item of value) headers.append(name, item);
        } else if (value !== undefined) {
          headers.set(name, value);
        }
      }
      finish(resolve, new Response(Readable.toWeb(res) as unknown as ReadableStream<Uint8Array>, {
        status: res.statusCode ?? 500,
        statusText: res.statusMessage ?? "",
        headers,
      }));
    });
    const onAbort = () => {
      const reason: unknown = request.signal?.reason;
      req.destroy();
      finish(reject, reason instanceof Error ? reason : new DOMException("The operation was aborted.", "AbortError"));
    };
    if (request.signal) {
      if (request.signal.aborted) {
        onAbort();
        return;
      }
      request.signal.addEventListener("abort", onAbort, { once: true });
    }
    req.setTimeout(0);
    req.on("error", error => finish(reject, error));
    if (bodyBuffer !== undefined) req.write(bodyBuffer);
    req.end();
  });
}

// Runtime proxy environment names are transport protocol controls, not model parameters.
const NATIVE_PROXY_VARIABLES = [
  "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy",
] as const;
export class BodyLimitError extends Error {
  constructor(readonly boundary: "request" | "response", options?: ErrorOptions) {
    super("The configured byte allowance was exceeded.", options);
  }
}

function awaitUntilCancelled<T>(pending: Promise<T>, signal: AbortSignal): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const onAbort = () => {
      signal.removeEventListener("abort", onAbort);
      reject(new Error("The bounded operation was cancelled."));
    };
    pending.then(value => {
      signal.removeEventListener("abort", onAbort);
      resolve(value);
    }, error => {
      signal.removeEventListener("abort", onAbort);
      reject(error);
    });
    if (signal.aborted) onAbort();
    else signal.addEventListener("abort", onAbort, { once: true });
  });
}

export async function cancelResponseBody(
  body: ReadableStream<Uint8Array> | null, signal: AbortSignal,
): Promise<void> {
  if (body !== null) await awaitUntilCancelled(body.cancel(), signal);
}

export async function readBoundedText(
  body: ReadableStream<Uint8Array> | null,
  maxBytes: number,
  signal: AbortSignal,
  boundary: "request" | "response" = "response",
): Promise<string> {
  if (body === null) throw new Error("The response body is absent.");
  const reader = body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    signal.throwIfAborted();
    while (true) {
      const next = await awaitUntilCancelled(reader.read(), signal);
      if (next.done) break;
      if (next.value.byteLength === 0) {
        await yieldRead();
        signal.throwIfAborted();
        continue;
      }
      size += next.value.byteLength;
      if (size > maxBytes) throw new BodyLimitError(boundary);
      chunks.push(next.value);
    }
    signal.throwIfAborted();
    const result = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) {
      result.set(chunk, offset);
      offset += chunk.byteLength;
    }
    const text = new TextDecoder("utf-8", { fatal: true }).decode(result);
    signal.throwIfAborted();
    return text;
  } catch (error) {
    try {
      await awaitUntilCancelled(reader.cancel(), signal);
    } catch (cleanup) {
      if (error instanceof BodyLimitError) {
        throw new BodyLimitError(error.boundary, {
          cause: new AggregateError([error, cleanup], "The bounded read and cancellation failed."),
        });
      }
      throw new AggregateError([error, cleanup], "The bounded read and cancellation failed.");
    }
    throw error;
  } finally {
    reader.releaseLock();
  }
}

export async function requestCompletion(
  runtime: ModelRuntime,
  payload: unknown,
  bounds: NativeBounds,
  signal?: AbortSignal,
  send: CompletionFetch = sendHttpRequest,
): Promise<unknown> {
  const body = JSON.stringify(payload);
  if (Buffer.byteLength(body, "utf8") > bounds.max_native_request_bytes) {
    throw new BodyLimitError("request");
  }
  if (NATIVE_PROXY_VARIABLES.some(name => Boolean(process.env[name]))) {
    throw new Error("Native generation does not accept environment proxy destinations.");
  }
  const deadline = new AbortController();
  const endsAt = performance.now() + runtime.timeout_seconds * 1000;
  const timeout = setTimeout(
    () => deadline.abort(new DOMException("The operation timed out.", "TimeoutError")),
    runtime.timeout_seconds * 1000,
  );
  const cancelled = signal === undefined ? deadline.signal : AbortSignal.any([signal, deadline.signal]);
  try {
    cancelled.throwIfAborted();
    const pending = send(new Request(new URL("/v1/chat/completions", runtime.base_url).href, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      redirect: "error",
      signal: cancelled,
    })).then(async response => {
      if (cancelled.aborted) {
        await cancelResponseBody(response.body, cancelled);
        cancelled.throwIfAborted();
      }
      return response;
    });
    const response = await awaitUntilCancelled(pending, cancelled);
    if (!response.ok) {
      await cancelResponseBody(response.body, cancelled);
      throw new Error("Native generation returned an unsuccessful response.");
    }
    const media = response.headers.get("content-type")?.split(";", 1)[0]?.trim();
    const encoding = response.headers.get("content-encoding");
    if (media !== "application/json" || (encoding !== null && encoding !== "identity")) {
      await cancelResponseBody(response.body, cancelled);
      throw new Error("Native generation returned an unsupported representation.");
    }
    const text = await readBoundedText(response.body, bounds.max_native_response_bytes, cancelled);
    const result: unknown = JSON.parse(text);
    if (performance.now() >= endsAt) deadline.abort();
    cancelled.throwIfAborted();
    return result;
  } finally {
    clearTimeout(timeout);
  }
}
