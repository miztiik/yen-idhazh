/** How does the actual native request boundary replay a named response without sockets? */
import { readFileSync } from "node:fs";
import path from "node:path";
import { Writable } from "node:stream";
import type { buildModelRequest } from "../../../../services/summary-generator/src/services/model-request.service.js";
import { loadModelRuntime, type ModelRuntime } from "../../../../services/summary-generator/src/config/load-model-runtime.js";
import type { CompletionFetch } from "../../../../services/summary-generator/src/services/request-completion.service.js";
import { repositoryRoot } from "../../../../services/summary-generator/test/model-recordings.js";

export type RecordedCall = {
  url: string; headers: Record<string, string>; data: ReturnType<typeof buildModelRequest>;
};
type RecordedModel = { runtime: ModelRuntime; calls: RecordedCall[]; send: CompletionFetch };
export async function withRecordedModel<T>(
  root: string, run: (recording: RecordedModel) => Promise<T>,
  options: { fixture?: string; waitForCalls?: number } = {},
): Promise<T> {
  const reply = readFileSync(path.join(repositoryRoot,
    options.fixture ?? "tests/fixtures/typescript-metadata/summarizer-model-response.json"));
  const calls: RecordedCall[] = [];
  const pending: ((response: Response) => void)[] = [];
  const send: CompletionFetch = async request => {
    calls.push({
      url: request.url,
      headers: Object.fromEntries(request.headers),
      data: JSON.parse(await request.text()),
    });
    return new Promise<Response>(resolve => {
      pending.push(resolve);
      if (calls.length >= (options.waitForCalls ?? 1)) {
        for (const complete of pending.splice(0).reverse()) {
          complete(new Response(reply, { headers: { "Content-Type": "application/json" } }));
        }
      }
    });
  };
  return run({ runtime: loadModelRuntime(root), calls, send });
}

export function recordOutput() {
  let value = "";
  const writer = new Writable({
    write(chunk, _encoding, done) { value += chunk.toString(); done(); },
  });
  return { writer, read: () => value };
}
