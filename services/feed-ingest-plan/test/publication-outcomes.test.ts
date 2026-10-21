/** Do actual publication identities, rather than planner selection, control attribution? */
import { beforeAll, expect, test } from "bun:test";
import { mkdtemp, mkdir, rm, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { z } from "zod";
import initializeParquet from "parquet-wasm/esm";
import { CONTRACT_VERSION, deriveUrlKey } from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import {
  DigestEventItemSchema, DigestPublicationSchema, ItemHealthPublicationSchema, PublishedRowSchema, RecordedEventPairSchema,
} from "../src/metrics/publication-evidence";
import type { DigestPublication, ItemHealthPublication } from "../src/metrics/publication-evidence";
import { readPublicationDay, reconcilePublication } from "../src/metrics/publication-outcomes";
import { readLedgerDay } from "../src/read-ledger-history/read-period";
import { settings, writer } from "./partition-fixtures";

beforeAll(async () => { await initializeParquet(); });
async function fixture() {
  const recorded = await Bun.file(new URL("../../../tests/fixtures/feed-ingest-plan/publication-evidence.json", import.meta.url)).json();
  const digest = DigestPublicationSchema.parse(recorded.digest);
  const health = recorded.health.map((row: unknown) => ItemHealthPublicationSchema.parse(row)) as ItemHealthPublication[];
  const published = digest.items.map(item => PublishedRowSchema.parse({
    version: CONTRACT_VERSION, published_on: digest.date, item_id: item.item_id, url_key: deriveUrlKey(item.source_url),
  }));
  return { recorded, digest, health, published };
}
test("read projections bind the recorded field sets, scalar types and terminal vocabularies", async () => {
  const { recorded } = await fixture();
  const bindings = recorded.bindings;
  expect(Object.keys(PublishedRowSchema.shape)).toEqual(bindings.PublishedRow.fields);
  for (const [name, type] of Object.entries(bindings.PublishedRow.types)) {
    const schema = z.toJSONSchema(PublishedRowSchema) as { properties: Record<string, { type: string }> };
    expect(type).toEqual(schema.properties[name]!.type);
  }
  expect(Object.keys(ItemHealthPublicationSchema.shape)).toEqual(bindings.ItemHealthPublication.fields);
  expect(ItemHealthPublicationSchema.shape.stage.options).toEqual(bindings.ItemHealthPublication.stages);
  expect(ItemHealthPublicationSchema.shape.outcome.options).toEqual(bindings.ItemHealthPublication.outcomes);
  expect(Object.keys(DigestPublicationSchema.shape)).toEqual(bindings.DigestPublication.fields);
  expect(Object.keys(DigestPublicationSchema.shape.runs.element.shape)).toEqual(bindings.DigestPublication.run_fields);
  expect(Object.keys(DigestPublicationSchema.shape.items.element.shape)).toEqual(bindings.DigestPublication.item_fields);
  expect(Object.keys(DigestPublicationSchema.shape.leads.unwrap().element.shape)).toEqual(bindings.DigestPublication.lead_fields);
  expect(Object.keys(DigestEventItemSchema.shape)).toEqual(bindings.DigestEventItem.fields);
  expect(Object.keys(RecordedEventPairSchema.shape)).toEqual(bindings.RecordedEventPair.fields);
  expect(RecordedEventPairSchema.shape.verdict.unwrap().options).toEqual(bindings.RecordedEventPair.verdicts);
  expect(RecordedEventPairSchema.shape.scorer_model.value).toBe(bindings.RecordedEventPair.scorer_model);
  expect(RecordedEventPairSchema.shape.judge_model.unwrap().options).toEqual(bindings.RecordedEventPair.judge_models);
});
test("native published Parquet retries and compact history retain recorded item/run attribution", async () => {
  const root = await mkdtemp(join(tmpdir(), "publication-native-"));
  try {
    const { digest, health, published } = await fixture();
    const contract = { schema: PublishedRowSchema, schemaVersion: CONTRACT_VERSION };
    const registry = { name: "published", family: "published", grain: "raw-and-compact" as const, lifecycle_status: "active" as const, prefix: ["published"] };
    const files = [];
    for (const attempt of [1, 2]) {
      const written = await persistLedger({
        ledger: "published", outputRoot: root, registryEntry: registry, ledgerSettings: settings,
        writerContext: writer("2026-10-19-1", attempt), rowContract: contract,
        period: { tier: "raw", covers: digest.date }, rows: published,
      });
      files.push(...written.files.map(file => join(root, file.path)));
    }
    const raw = await readLedgerDay({ ledger: "published", day: digest.date, rawFiles: files, contract });
    expect(raw.rows.map(row => row.identity.attempt)).toEqual([1, 2]);
    const compact = await persistLedger({
      ledger: "published", outputRoot: root, registryEntry: registry, ledgerSettings: settings,
      writerContext: { ...writer("2026-10-20-1", 9), producer: "tests.publication.compactor" },
      rowContract: contract, period: { tier: "compact", period: "monthly", covers: "2026-10", builtFrom: 2 }, rows: raw.rows,
    });
    const file = compact.files[0]!;
    const index = join(root, "compact", "published", "index", "monthly.json");
    await mkdir(dirname(index), { recursive: true });
    await writeFile(index, JSON.stringify({
      version: "2026-10-07", ledger: "published", period: "monthly",
      entries: [{ covers: "2026-10", rows: 2, bytes: (await stat(join(root, file.path))).size, state: "packed" }],
    }));
    const packed = await readLedgerDay({ ledger: "published", day: digest.date, indexes: { monthly: index }, contract });
    const outcome = reconcilePublication({
      run_id: "2026-10-19-1", digest,
      published: { ...packed, rows: packed.rows.map(row => row.row) },
      health: { day: digest.date, status: "rows", rows: [...health, ...health] },
    });
    expect(outcome.availability).toBe("available");
    expect(outcome.articles).toEqual([{
      date: digest.date, run_id: "2026-10-19-1", item_id: "ai-01", url_key: published[0]!.url_key,
      source_id: "source-0", source_kind: "reporting", lead: true,
    }]);
    expect(packed.rows.map(row => row.identity.attempt)).toEqual([1, 2]);
    const digestPath = join(root, "digest.json");
    await writeFile(digestPath, JSON.stringify(digest));
    const observed = await readPublicationDay({
      published: { day: digest.date, indexes: { monthly: index }, schema_version: CONTRACT_VERSION },
      health: { day: digest.date, status: "rows", rows: health }, digest_path: digestPath,
    });
    expect(observed.publication.articles).toEqual(outcome.articles);
    expect(observed.outcomes.find(run => run.run_id === "2026-10-19-2")!.articles).toEqual([]);
    expect((await readPublicationDay({
      published: { day: digest.date, indexes: { monthly: index }, schema_version: CONTRACT_VERSION },
      health: { day: digest.date, status: "rows", rows: health }, digest_path: join(root, "absent-digest.json"),
    })).publication.status).toBe("missing");
  } finally { await rm(root, { recursive: true, force: true }); }
});
test("repeated runs, zero publication and legacy ordinals never become latest-run guesses", async () => {
  const { digest, published, health } = await fixture();
  const input = {
    published: { day: digest.date, status: "rows" as const, rows: published },
    health: { day: digest.date, status: "rows" as const, rows: health }, digest,
  };
  expect(reconcilePublication({ ...input, run_id: "2026-10-19-2" }).articles).toEqual([]);
  expect(reconcilePublication({ ...input, run_id: "2026-10-19-2" }).availability).toBe("available");
  const legacy: DigestPublication = { ...digest, runs: digest.runs.map(run => ({ ...run, run_id: null })) };
  expect(reconcilePublication({ ...input, digest: legacy, run_id: "2026-10-19-1" }).articles).toHaveLength(1);
  const missingHealth = { day: digest.date, status: "missing" as const, rows: [] };
  const unknown = reconcilePublication({ ...input, digest: legacy, health: missingHealth, run_id: "2026-10-19-2" });
  expect(unknown.availability).toBe("unavailable");
  expect(unknown.articles).toEqual([]);
  expect(unknown.unattributed_item_ids).toEqual(["ai-01"]);
});
test("selected items alone, absent manifests, conflicting joins and absent kind stay explicit", async () => {
  const { digest, published } = await fixture();
  const input = {
    run_id: "2026-10-19-1", digest,
    published: { day: digest.date, status: "empty" as const, rows: [] },
    health: { day: digest.date, status: "empty" as const, rows: [] },
  };
  expect(reconcilePublication(input).availability).toBe("unavailable");
  expect(reconcilePublication({ ...input, digest: null }).unavailable_reason).toBe("missing_publication");
  expect(() => reconcilePublication({ ...input, published: {
    day: digest.date, status: "rows", rows: [{ ...published[0]!, url_key: "a".repeat(64) }],
  } })).toThrow("URL identities disagree");
  const unlabelled = { ...digest, items: digest.items.map(({ source_kind: _kind, ...item }) => item) };
  const outcome = reconcilePublication({ ...input, digest: unlabelled,
    published: { day: digest.date, status: "rows", rows: published } });
  expect(outcome.articles[0]!.source_kind).toBeNull();
});
test("conflicting unsettled terminal health rows refuse attribution; known other runs do not poison zero runs", async () => {
  const { digest, health, published } = await fixture();
  const success = health[0]!;
  const input = {
    run_id: "2026-10-19-1", digest, published: { day: digest.date, status: "rows" as const, rows: published },
    health: { day: digest.date, status: "rows" as const, rows: health },
  };
  expect(reconcilePublication(input).articles).toHaveLength(1);
  expect(() => reconcilePublication({ ...input, health: { ...input.health, rows: [success, { ...success, outcome: "failed" }] } })).toThrow("Conflicting");
  const missingOther = { ...digest, items: [], leads: [], runs: digest.runs.map(run => ({ ...run, items_added: 0 })) };
  expect(reconcilePublication({ ...input, run_id: "2026-10-19-2", digest: missingOther }).availability).toBe("available");
  expect(reconcilePublication({ ...input, digest: missingOther }).availability).toBe("unavailable");
});
test("the recorded run can finish after midnight without changing its publication day", async () => {
  const { digest, health, published } = await fixture();
  const outcome = reconcilePublication({
    run_id: "2026-10-19-1", digest: { ...digest, generated_at: "2026-10-20T00:01:00Z" },
    published: { day: digest.date, status: "rows", rows: published },
    health: { day: digest.date, status: "rows", rows: health },
  });
  expect(outcome.availability).toBe("available");
  expect(outcome.articles[0]!.date).toBe("2026-10-19");
});
test("a named known-empty publication day needs no invented digest; a missing manifest is not empty", async () => {
  const input = {
    published: { day: "2026-10-19", rawFiles: [] as string[], schema_version: CONTRACT_VERSION },
    health: { day: "2026-10-19", status: "missing" as const, rows: [] }, digest_path: null,
  };
  expect((await readPublicationDay(input)).publication).toEqual({ day: "2026-10-19", status: "empty", articles: [] });
  expect((await readPublicationDay({ ...input, published: { day: "2026-10-19", schema_version: CONTRACT_VERSION } })).publication.status).toBe("missing");
});
