/** Does real selection-to-dispatch allocation preserve content and deterministic worker choices? */
import { expect, test } from "bun:test";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { CONTRACT_VERSION, FeedIngestDispatchSchema } from "@idhazh/common-contracts";
import { partitionArticles, persistDispatches } from "../src/partition-article-shards/shard-packer";
import { resolvePartitionRequest } from "../src/partition-article-shards/partition-input";
import { readCurrentSelections } from "../src/partition-article-shards/read-editorial-selection";
import { fixtureInput, readWritten, registration, settings, writer } from "./partition-fixtures";

test("uneven real curated selections have exact greedy assignments and lower spread than round robin", async () => {
  const root = await mkdtemp(join(tmpdir(), "partition-uneven-"));
  try {
    const input = await fixtureInput(root);
    const articles = await readCurrentSelections({
      curation: input.curation, persisted: input.persisted.selections, candidates: input.candidates,
      writer: writer(input.fixture.run_id), outputRoot: root, context: input.context,
    });
    expect(articles.map(article => article.content.word_count)).toEqual(input.fixture.word_work);
    const base = {
      selections: articles.map(article => article.selection), candidates: input.candidates,
      context: input.context, settings: input.planning.config.partition,
    };
    const packed = partitionArticles({ ...base, request: { strategy: "bin-pack", shards: 2 } });
    const round = partitionArticles({ ...base, request: { strategy: "round-robin", shards: 2 } });
    expect(packed.dispatches.map(row => row.partition.worker_assignment)).toEqual(input.fixture.bin_pack_workers);
    expect(packed.work).toEqual(input.fixture.bin_pack_work);
    expect(round.dispatches.map(row => row.partition.worker_assignment)).toEqual(input.fixture.round_robin_workers);
    expect(round.work).toEqual(input.fixture.round_robin_work);
    const spread = (work: number[]) => Math.max(...work) - Math.min(...work);
    expect(spread(packed.work)).toBeLessThan(spread(round.work));
    expect(partitionArticles({ ...base, selections: [...base.selections].reverse(), candidates: [...base.candidates].reverse(),
      request: { strategy: "bin-pack", shards: 2 } })).toEqual(packed);
    const stored = await persistDispatches(packed, {
      outputRoot: root, writerContext: writer(input.fixture.run_id, 1, 5),
      ledgerSettings: settings, registration: registration("dispatches"), date: input.fixture.date,
    });
    const history = await readWritten(root, "dispatches", input.fixture.date,
      { schema: FeedIngestDispatchSchema, schemaVersion: CONTRACT_VERSION }, stored);
    expect(history.rows.map(held => held.row)).toEqual(packed.dispatches);
    expect(history.rows.every(held => held.identity.shard === 5)).toBe(true);
    for (const row of packed.dispatches) {
      expect(row.selection).toEqual(input.curation.rows.find(selection => selection.candidate_id === row.selection.candidate_id)!);
      expect(row.content).toEqual(input.candidates.find(candidate => candidate.candidate_id === row.content.candidate_id)!);
    }
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("equal work, fewer articles, empty selection and none keep exact selected identities", async () => {
  const root = await mkdtemp(join(tmpdir(), "partition-bounds-"));
  try {
    const input = await fixtureInput(root, { words: [4, 4, 4] });
    const base = {
      selections: input.curation.rows, candidates: input.candidates,
      context: input.context, settings: input.planning.config.partition,
    };
    for (const strategy of ["bin-pack", "round-robin"] as const) {
      const equal = partitionArticles({ ...base, request: { strategy, shards: 2 } });
      expect(equal.dispatches.map(row => row.partition.worker_assignment)).toEqual([0, 1, 0]);
      expect(equal.work).toEqual([8, 4]);
      const fewer = partitionArticles({ ...base, selections: base.selections.slice(0, 1), request: { strategy, shards: 4 } });
      expect(fewer.work).toEqual([4, 0, 0, 0]);
    }
    const none = partitionArticles({ ...base, request: { strategy: "none" } });
    expect(none.dispatch_count).toBe(1);
    expect(none.dispatches.every(row => row.partition.worker_assignment === 0)).toBe(true);
    expect(none.work).toEqual([12]);
    const empty = await fixtureInput(root, { count: 0 });
    expect(await readCurrentSelections({
      curation: empty.curation, persisted: empty.persisted.selections, candidates: [],
      context: empty.context, outputRoot: root, writer: writer(empty.fixture.run_id),
    })).toEqual([]);
    const result = partitionArticles({ ...base, selections: [], candidates: [] });
    expect(result.work).toEqual([0, 0, 0, 0]);
    expect(result.dispatches).toEqual([]);
    expect(await persistDispatches(result, {
      outputRoot: root, writerContext: writer(empty.fixture.run_id), ledgerSettings: settings,
      registration: registration("dispatches"), date: empty.fixture.date,
    })).toEqual({ status: "empty", files: [] });
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("request-only validation refuses invalid counts before any content or harvest is required", () => {
  const config = { default_strategy: "bin-pack" as const, default_shards: 4, min_shards: 2, max_shards: 8 };
  expect(resolvePartitionRequest(config)).toEqual({ strategy: "bin-pack", dispatch_count: 4 });
  expect(resolvePartitionRequest(config, { strategy: "none" })).toEqual({ strategy: "none", dispatch_count: 1 });
  expect(resolvePartitionRequest(config, { strategy: "none", shards: 1 }).dispatch_count).toBe(1);
  for (const shards of [0, -1, 1, 9, 1.5, NaN, Infinity]) {
    expect(() => resolvePartitionRequest(config, { shards })).toThrow();
  }
  expect(() => resolvePartitionRequest(config, { strategy: "none", shards: 2 })).toThrow("none");
  expect(() => resolvePartitionRequest({ ...config, default_shards: 9 })).toThrow();
  expect(() => resolvePartitionRequest({ ...config, min_shards: 10 })).toThrow();
});

test("missing content and changed source, policy, labels, context or ranks are refused without mutation", async () => {
  const root = await mkdtemp(join(tmpdir(), "partition-invalid-"));
  try {
    const input = await fixtureInput(root, { count: 1 });
    const base = {
      selections: input.curation.rows, candidates: input.candidates,
      context: input.context, settings: input.planning.config.partition,
    };
    const snapshot = structuredClone(base);
    expect(() => partitionArticles({ ...base, candidates: [] })).toThrow("Missing original content");
    expect(() => partitionArticles({ ...base, candidates: [...base.candidates, ...base.candidates] })).toThrow("Repeated");
    expect(() => partitionArticles({ ...base, selections: [...base.selections, ...base.selections] })).toThrow("distinct");
    const changed = [
      { policy: { ...base.selections[0]!.policy, max_age_hours: 2 } },
      { source: { ...base.selections[0]!.source, title: "Different snapshot" } },
      { labels: { ...base.selections[0]!.labels, origin: "different", matcher_version: "different" } },
      { correlation_id: "another-correlation" },
      { date: "2026-10-22" },
    ];
    for (const patch of changed) expect(() => partitionArticles({
      ...base, selections: [{ ...base.selections[0]!, ...patch }],
    })).toThrow();
    const persisted = structuredClone(input.persisted.selections);
    if (persisted.status === "written") persisted.files[0]!.content_sha256 = "0".repeat(64);
    await expect(readCurrentSelections({
      curation: input.curation, persisted, candidates: input.candidates,
      context: input.context, writer: writer(input.fixture.run_id), outputRoot: root,
    })).rejects.toThrow("write result");
    expect(base).toEqual(snapshot);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("a consistent freshness override passes actual screening, curation and dispatch without changing originals", async () => {
  const root = await mkdtemp(join(tmpdir(), "partition-override-"));
  try {
    const input = await fixtureInput(root, { count: 2, freshness: 72 });
    const original = structuredClone(input.candidates);
    const articles = await readCurrentSelections({
      curation: input.curation, persisted: input.persisted.selections, candidates: input.candidates,
      context: input.context, writer: writer(input.fixture.run_id), outputRoot: root,
    });
    const result = partitionArticles({
      selections: articles.map(article => article.selection), candidates: input.candidates,
      context: input.context, settings: input.planning.config.partition,
    });
    expect(result.dispatches).toHaveLength(2);
    expect(result.dispatches.every(row => row.content.policy.max_age_hours === 72 && row.selection.policy.max_age_hours === 72)).toBe(true);
    expect(input.candidates).toEqual(original);
  } finally { await rm(root, { recursive: true, force: true }); }
});
