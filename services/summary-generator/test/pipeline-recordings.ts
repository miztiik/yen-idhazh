/** How do real local transports replay named model responses without inference? */
import http from "node:http";
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { loadModelRuntime, type ModelRuntime } from "../src/config/load-model-runtime.js";
import { readJson, repositoryRoot } from "./model-recordings.js";

type RecordedCall = { headers: http.IncomingHttpHeaders; data: unknown };
type RecordedModel = { runtime: ModelRuntime; calls: RecordedCall[] };

export async function listen(server: http.Server): Promise<string> {
  await new Promise<void>(resolve => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("Expected an ephemeral loopback port.");
  return `http://127.0.0.1:${address.port}`;
}

export async function close(server: http.Server): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    server.close(error => error ? reject(error) : resolve());
    server.closeAllConnections();
  });
}

export async function withRecordedModel<T>(
  root: string,
  run: (recording: RecordedModel) => Promise<T>,
  options: { fixture?: string; waitForCalls?: number } = {},
): Promise<T> {
  const reply = readFileSync(path.join(
    repositoryRoot,
    options.fixture ?? "tests/fixtures/typescript-metadata/summarizer-model-response.json",
  ));
  const calls: RecordedCall[] = [];
  const pending: http.ServerResponse[] = [];
  const server = http.createServer((request, response) => {
    let body = "";
    request.on("data", chunk => { body += chunk; });
    request.on("end", () => {
      calls.push({ headers: request.headers, data: JSON.parse(body) });
      pending.push(response);
      if (calls.length >= (options.waitForCalls ?? 1)) {
        for (const held of pending.splice(0).reverse()) {
          held.writeHead(200, { "Content-Type": "application/json" });
          held.end(reply);
        }
      }
    });
  });
  const baseUrl = await listen(server);
  try {
    const pointer = readJson("config/idhazh.json");
    pointer.models_file = "models/independent-substitution.json";
    pointer.model_server.base_url = baseUrl;
    writeFileSync(path.join(root, "idhazh.json"), JSON.stringify(pointer));
    return await run({ runtime: loadModelRuntime(root), calls });
  } finally {
    await close(server);
  }
}
