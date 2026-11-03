/** Do real event producers and consumers retain application values and operation relationships? */
import { expect, test } from "bun:test";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createCloudEvent } from "@idhazh/common-contracts/create-cloud-event";
import { readCloudEvent } from "@idhazh/common-contracts/read-cloud-event";
import { createChildContext, createRootContext } from "@idhazh/common-contracts/create-operation-context";
import { loadEventSources } from "@idhazh/common-contracts/load-event-sources";
import { readTraceContext, writeTraceContext } from "@idhazh/common-contracts/propagate-trace-context";
import { OperationMetadataSchema } from "@idhazh/common-contracts/schemas/operation-metadata";
import { readSelectedArticlesArtifact } from "../src/schemas/selected-article.schema";

const sourcePath = new URL("../../../config/typescript-event-sources.json", import.meta.url);
const recordingPath = new URL("../../../tests/fixtures/feed-ingest-plan/entry-points/selected-articles.json", import.meta.url);

test("distinct occurrences replay unchanged and a consumer recovers the recorded selected articles", async () => {
  const sources = await loadEventSources(sourcePath);
  const data = readSelectedArticlesArtifact(await Bun.file(recordingPath).json());
  const context = createRootContext({ traceState: "reader=value" });
  const input = {
    source: sources.planner, type: "planner.selected", context, data,
    parseData: readSelectedArticlesArtifact,
  };
  const first = createCloudEvent(input);
  const second = createCloudEvent(input);
  expect(first.id).not.toBe(second.id);
  expect(first.traceparent).toBe(second.traceparent);
  const saved = JSON.stringify(first);
  const replayed = readCloudEvent(JSON.parse(saved), readSelectedArticlesArtifact);
  expect(replayed).toEqual(first);
  expect(replayed.data).toEqual(data);
  expect(JSON.stringify(replayed)).toBe(saved);

  const received = OperationMetadataSchema.parse(readTraceContext({
    traceparent: replayed.traceparent, tracestate: replayed.tracestate,
  }));
  const consumer = createChildContext(received, {
    links: [{ traceId: received.traceId, spanId: received.spanId }],
  });
  expect(consumer.traceId).toBe(context.traceId);
  expect(consumer.parentSpanId).toBe(context.spanId);
  expect(consumer.spanId).not.toBe(context.spanId);
  expect(consumer.traceState).toBe(context.traceState);
  expect(consumer.links[0]).toEqual({ traceId: context.traceId, spanId: context.spanId });
});

test("an enclosing operation and a completed input remain separate even across executions", () => {
  const enclosing = createRootContext();
  const input = createRootContext();
  const consumer = createChildContext(enclosing, {
    links: [{ traceId: input.traceId, spanId: input.spanId }],
  });
  expect(input.traceId).not.toBe(enclosing.traceId);
  expect(consumer.traceId).toBe(enclosing.traceId);
  expect(consumer.parentSpanId).toBe(enclosing.spanId);
  expect(consumer.links).toEqual([{ traceId: input.traceId, spanId: input.spanId }]);
  const continuation = createRootContext({ links: consumer.links });
  expect(continuation.traceId).not.toBe(consumer.traceId);
  expect(continuation.parentSpanId).toBeUndefined();
  expect(continuation.links).toEqual(consumer.links);
});

test("the W3C codec retains valid incoming state and emits unsampled child context", () => {
  const incoming = readTraceContext({
    traceparent: "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
    tracestate: ["first=value", "second=other"],
  });
  const parent = OperationMetadataSchema.parse(incoming);
  const child = createChildContext(parent);
  const carrier = writeTraceContext(child);
  expect(carrier.traceparent).toBe(`00-${parent.traceId}-${child.spanId}-00`);
  expect(carrier.tracestate).toBe("first=value,second=other");
  expect(readTraceContext(carrier)).toEqual({
    traceId: child.traceId, spanId: child.spanId, links: [], traceState: parent.traceState,
  });
});

test.each([
  undefined,
  "not-a-context",
  "00-00000000000000000000000000000000-00f067aa0ba902b7-00",
  "00-4bf92f3577b34da6a3ce929d0e0e4736-0000000000000000-00",
  "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-00-extra",
  "ff-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-00",
])("an absent or invalid optional carrier cannot supply a parent: %s", traceparent => {
  expect(readTraceContext({ traceparent, tracestate: "first=value" })).toBeUndefined();
  const fresh = createRootContext();
  expect(fresh.parentSpanId).toBeUndefined();
  expect(OperationMetadataSchema.parse(fresh)).toEqual(fresh);
});

test("invalid optional state does not replace valid incoming operation identity", () => {
  const parent = createRootContext();
  const received = readTraceContext({ ...writeTraceContext(parent), tracestate: "not-valid-state" });
  expect(received).toEqual({ traceId: parent.traceId, spanId: parent.spanId, links: [] });
});

test("interleaved operations retain their own execution, state and input links", async () => {
  const roots = [
    createRootContext({ traceState: "first=value" }),
    createRootContext({ traceState: "second=other" }),
  ];
  const children = await Promise.all(roots.map(async root => {
    const incoming = OperationMetadataSchema.parse(readTraceContext(writeTraceContext(root)));
    await Promise.resolve();
    return createChildContext(incoming, { links: [{ traceId: root.traceId, spanId: root.spanId }] });
  }));
  for (const [index, root] of roots.entries()) {
    const child = OperationMetadataSchema.parse(children[index]);
    expect(child.traceId).toBe(root.traceId);
    expect(child.parentSpanId).toBe(root.spanId);
    expect(child.traceState).toBe(root.traceState);
    expect(child.links).toEqual([{ traceId: root.traceId, spanId: root.spanId }]);
  }
});

test("invalid identity and self-parentage cannot leave the native boundary", () => {
  const root = createRootContext();
  for (const patch of [
    { traceId: "0".repeat(32) }, { spanId: "0".repeat(16) },
    { traceId: "A".repeat(32) }, { spanId: "a".repeat(15) },
    { parentSpanId: root.spanId }, { parentSpanId: null },
    { links: [{ traceId: root.traceId, spanId: "0".repeat(16) }] },
    { traceState: "not-valid-state" },
  ]) {
    expect(() => OperationMetadataSchema.parse({ ...root, ...patch })).toThrow();
  }
});

test("both producers and replay consumers use the real application validator", async () => {
  const sources = await loadEventSources(sourcePath);
  const data = readSelectedArticlesArtifact(await Bun.file(recordingPath).json());
  const input = {
    source: sources.planner, type: "planner.selected", context: createRootContext(),
    data, parseData: readSelectedArticlesArtifact,
  };
  const event = createCloudEvent(input);
  const invalid = { ...data, attempt: 0 };
  expect(() => createCloudEvent({ ...input, data: invalid })).toThrow("attempt");
  expect(() => readCloudEvent({ ...event, data: invalid }, readSelectedArticlesArtifact)).toThrow("attempt");
  expect(() => readCloudEvent({ ...event, traceparent: "invalid" }, readSelectedArticlesArtifact))
    .toThrow("traceparent");
});

test("explicit source loading changes producer identity and refuses missing or invalid settings", async () => {
  const directory = await mkdtemp(join(tmpdir(), "event-sources-"));
  const path = join(directory, "sources.json");
  try {
    const configured = await loadEventSources(sourcePath);
    const changed = { ...configured, planner: "/operators/planner" };
    await writeFile(path, JSON.stringify(changed));
    const sources = await loadEventSources(path);
    const data = readSelectedArticlesArtifact(await Bun.file(recordingPath).json());
    const event = createCloudEvent({
      source: sources.planner, type: "planner.selected", context: createRootContext(),
      data, parseData: readSelectedArticlesArtifact,
    });
    expect(event.source).toBe(changed.planner);
    const { planner: _planner, ...missing } = changed;
    await writeFile(path, JSON.stringify(missing));
    await expect(loadEventSources(path)).rejects.toThrow("planner");
    for (const planner of ["has spaces", "/bad%escape", "https://[invalid", ""]) {
      await writeFile(path, JSON.stringify({ ...changed, planner }));
      await expect(loadEventSources(path)).rejects.toThrow("planner");
    }
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
