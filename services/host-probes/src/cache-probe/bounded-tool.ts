/** How is one trusted measurement subprocess bounded and closed without signalling its target? */
import { spawn } from "node:child_process";
import type { CacheReason } from "./cache-schema";

export type ToolOutput = {
  code: number | null; signal: NodeJS.Signals | null; reason: CacheReason | null;
  stdout: string; stderr: string;
};
export function startBoundedTool(
  program: "perf" | "multichase", args: readonly string[],
  bounds: { max_output_bytes: number; timeout_ms: number }, signal?: AbortSignal,
) {
  const child = spawn(program, args, {
    stdio: ["pipe", "pipe", "pipe"],
    env: { ...process.env, LC_ALL: "C", LANG: "C", PERF_CONFIG: "/dev/null" },
    windowsHide: true,
  });
  let active = true;
  let reason: CacheReason | null = null;
  let stdout = "", stderr = "", bytes = 0;
  const observers = new Set<(chunk: string) => void>();
  let started: (pid: number | null) => void;
  const ready = new Promise<number | null>(resolve => { started = resolve; });
  const stop = (cause: CacheReason, force = true) => {
    reason ??= cause;
    if (active) child.kill(force ? "SIGKILL" : "SIGINT");
  };
  const abort = () => stop("cancelled");
  const timer = setTimeout(() => stop("timeout"), bounds.timeout_ms);
  signal?.addEventListener("abort", abort, { once: true });
  if (signal?.aborted) abort();
  const consume = (stream: "stdout" | "stderr", chunk: Buffer) => {
    bytes += chunk.byteLength;
    if (bytes > bounds.max_output_bytes) { stop("output_limit"); return; }
    const text = chunk.toString("utf8");
    if (stream === "stdout") {
      stdout += text;
      for (const observe of observers) observe(text);
    } else stderr += text;
  };
  child.stdout.on("data", (chunk: Buffer) => consume("stdout", chunk));
  child.stderr.on("data", (chunk: Buffer) => consume("stderr", chunk));
  child.once("spawn", () => started(child.pid ?? null));
  child.once("error", (error: NodeJS.ErrnoException) => {
    reason ??= error.code === "ENOENT" ? "tool_missing"
      : error.code === "EACCES" || error.code === "EPERM" ? "permission_denied" : "tool_failed";
    started(null);
  });
  // A closed stdin is expected when perf rejects an event before reading control commands.
  child.stdin.on("error", (error: NodeJS.ErrnoException) => {
    if (error.code !== "EPIPE" && error.code !== "ERR_STREAM_DESTROYED") stop("tool_failed");
  });
  const finished = new Promise<ToolOutput>(resolve => {
    child.once("close", (code, signal) => {
      active = false;
      clearTimeout(timer);
      resolve({ code, signal, reason, stdout, stderr });
    });
  }).finally(() => {
    signal?.removeEventListener("abort", abort);
    observers.clear();
  });
  return {
    ready, finished,
    get running() { return active; },
    interrupt() { if (active) child.kill("SIGINT"); },
    cancel(cause: CacheReason = "cancelled") { stop(cause); },
    async control(command: "enable" | "disable", timeoutMs: number): Promise<boolean> {
      let acknowledge: (value: boolean) => void;
      const ack = new Promise<boolean>(resolve => { acknowledge = resolve; });
      let pending = "";
      const observe = (chunk: string) => {
        pending += chunk.replaceAll("\0", "");
        if (pending === "ack\n") acknowledge(true);
        else if (pending.includes("\n")) acknowledge(false);
      };
      observers.add(observe);
      const timeout = setTimeout(() => acknowledge(false), timeoutMs);
      try {
        if (!active || child.stdin.destroyed) return false;
        child.stdin.write(`${command}\n`);
        return await Promise.race([ack, finished.then(() => false)]);
      } finally {
        clearTimeout(timeout);
        observers.delete(observe);
      }
    },
  };
}
