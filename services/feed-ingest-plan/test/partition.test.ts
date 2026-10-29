/** Does packing preserve the single chosen content population and deterministic worker choices? */
import { expect, test } from "bun:test";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { SelectedArticleRowContract, selectedArticleMetadata } from "@idhazh/common-contracts";
import { partitionArticles } from "../src/partition-article-shards/shard-packer";
import { resolvePartitionRequest } from "../src/partition-article-shards/partition-input";
import { fixtureInput, readWritten, writeRows } from "./partition-fixtures";

test("uneven real curated selections have exact greedy assignments and lower spread than round robin", async () => {
  const root = await mkdtemp(join(tmpdir(), "partition-uneven-"));
  try {
    const input = await fixtureInput(root);
    const articles = input.curation.articles;
    expect(articles.map(article => article.estimated_work)).toEqual(input.fixture.word_work);
    const packed = partitionArticles(articles, { strategy: "bin-pack", dispatch_count: 2 });
    const round = partitionArticles(articles, { strategy: "round-robin", dispatch_count: 2 });
    expect(packed.articles.map(row => row.worker_assignment)).toEqual(input.fixture.bin_pack_workers);
    expect(packed.work).toEqual(input.fixture.bin_pack_work);
    expect(round.articles.map(row => row.worker_assignment)).toEqual(input.fixture.round_robin_workers);
    expect(round.work).toEqual(input.fixture.round_robin_work);
    const spread = (work: number[]) => Math.max(...work) - Math.min(...work);
    expect(spread(packed.work)).toBeLessThan(spread(round.work));
    expect(partitionArticles([...articles].reverse(), { strategy: "bin-pack", dispatch_count: 2 })).toEqual(packed);
    const metadata = packed.articles.map(article => ({
      ...selectedArticleMetadata(article), run_id: article.run_id, attempt: article.attempt, date: article.date,
    }));
    const written = await writeRows(root, "selected-articles", input.fixture.date, SelectedArticleRowContract, metadata);
    const history = await readWritten(root, "selected-articles", input.fixture.date, SelectedArticleRowContract, written);
    expect(history.rows).toEqual(metadata);
    expect(history.rows.every(row => !("article_text" in row) && !("unit_id" in row))).toBe(true);
    expect(packed.articles.map(({ worker_assignment: _worker, ...article }) => article))
      .toEqual(articles.map(({ worker_assignment: _worker, ...article }) => article));
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("equal work, fewer articles, empty selection and none keep exact selected identities", async () => {
  const root = await mkdtemp(join(tmpdir(), "partition-bounds-"));
  try {
    const input = await fixtureInput(root, { words: [4, 4, 4] });
    const articles = input.curation.articles;
    for (const strategy of ["bin-pack", "round-robin"] as const) {
      const equal = partitionArticles(articles, { strategy, dispatch_count: 2 });
      expect(equal.articles.map(row => row.worker_assignment)).toEqual([0, 1, 0]);
      expect(equal.work).toEqual([8, 4]);
      expect(partitionArticles(articles.slice(0, 1), { strategy, dispatch_count: 4 }).work).toEqual([4, 0, 0, 0]);
    }
    const none = partitionArticles(articles, { strategy: "none", dispatch_count: 1 });
    expect(none.articles.every(row => row.worker_assignment === 0)).toBe(true);
    expect(none.work).toEqual([12]);
    const empty = await fixtureInput(root, { count: 0 });
    expect(empty.written).toEqual({ status: "empty", files: [] });
    expect(partitionArticles([], { strategy: "bin-pack", dispatch_count: 4 }))
      .toEqual({ strategy: "bin-pack", dispatch_count: 4, work: [0, 0, 0, 0], articles: [] });
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("request-only validation refuses invalid counts before any content or harvest is required", () => {
  const config = { default_strategy: "bin-pack" as const, default_shards: 4, min_shards: 2, max_shards: 8 };
  expect(resolvePartitionRequest(config)).toEqual({ strategy: "bin-pack", dispatch_count: 4 });
  expect(resolvePartitionRequest(config, { strategy: "none" })).toEqual({ strategy: "none", dispatch_count: 1 });
  expect(resolvePartitionRequest(config, { strategy: "none", shards: 1 }).dispatch_count).toBe(1);
  for (const shards of [0, -1, 1, 9, 1.5, NaN, Infinity]) expect(() => resolvePartitionRequest(config, { shards })).toThrow();
  expect(() => resolvePartitionRequest(config, { strategy: "none", shards: 2 })).toThrow("none");
  expect(() => resolvePartitionRequest({ ...config, default_shards: 9 })).toThrow();
  expect(() => resolvePartitionRequest({ ...config, min_shards: 10 })).toThrow();
});

test("missing content, duplicate URLs and invalid ranks are refused without mutation", async () => {
  const root = await mkdtemp(join(tmpdir(), "partition-invalid-"));
  try {
    const { curation } = await fixtureInput(root, { count: 1 });
    const articles = curation.articles;
    const snapshot = structuredClone(articles);
    const controls = { strategy: "bin-pack" as const, dispatch_count: 2 };
    expect(() => partitionArticles([{ ...articles[0]!, article_text: undefined } as never], controls)).toThrow();
    expect(() => partitionArticles([...articles, ...articles], controls)).toThrow("distinct");
    for (const patch of [{ editorial_rank: 2 }, { estimated_work: -1 }, { worker_assignment: -1 }, { article_text: null }]) {
      expect(() => partitionArticles([{ ...articles[0]!, ...patch } as never], controls)).toThrow();
    }
    expect(articles).toEqual(snapshot);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("packing retains actual timing, accounting dates and text rather than reconstructing a dispatch payload", async () => {
  const root = await mkdtemp(join(tmpdir(), "partition-cross-stage-"));
  try {
    const input = await fixtureInput(root, { count: 1 });
    const publication = "2026-10-20T23:55:00Z";
    const article = { ...input.curation.articles[0]!, published_at: publication, timing_at: publication, age_hours: 12 + 5 / 60 };
    const packed = partitionArticles([article], { strategy: "none", dispatch_count: 1 });
    expect(packed.articles[0]).toEqual({ ...article, worker_assignment: 0 });
    expect(article.worker_assignment).toBeNull();
    const row = {
      ...selectedArticleMetadata(packed.articles[0]!), date: article.date, run_id: article.run_id, attempt: article.attempt,
    };
    const written = await writeRows(root, "selected-articles", input.fixture.date, SelectedArticleRowContract, [row]);
    expect((await readWritten(root, "selected-articles", input.fixture.date, SelectedArticleRowContract, written)).rows).toEqual([row]);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("configured screening, curation and packing preserve chosen originals", async () => {
  const root = await mkdtemp(join(tmpdir(), "partition-configured-"));
  try {
    const input = await fixtureInput(root, { count: 2 });
    const original = structuredClone(input.candidates);
    expect(input.screening.admitted).toHaveLength(2);
    const result = partitionArticles(input.curation.articles, { strategy: "bin-pack", dispatch_count: 2 });
    expect(result.articles).toHaveLength(2);
    expect(result.articles.map(article => article.article_text)).toEqual(original.map(candidate => candidate.article_text));
    expect(input.candidates).toEqual(original);
    expect(result.articles.every(article => !("policy" in article) && !("labels" in article))).toBe(true);
  } finally { await rm(root, { recursive: true, force: true }); }
});
