/** Recover old keys only from the current offer or bounded, verified saved addresses. */
import { expect, test } from "bun:test";
import { mkdtemp, rm, mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { z } from "zod";
import {
  DiscoveredArticleRowSchema, DiscoveredArticleRowContract, SelectedArticleRowContract,
  LEGACY_SELECTED_ARTICLE_VERSION, selectedArticleMetadata, ParsedFeedBatchSchema,
} from "@idhazh/common-contracts";
import { ArticleIdentityEvidence } from "../src/read-ledger-history/article-identity-evidence";
import { readArticleIdentityHistory } from "../src/read-ledger-history/read-article-identity-history";
import { deriveArticleIdentity } from "../src/harvest-feeds/article-identity";
import { deriveLegacyArticleIdentity } from "../src/harvest-feeds/legacy-article-identity";
import { rememberDiscoveries } from "../src/read-ledger-history/read-discovered-evidence";
import { prepareArticle } from "../src/harvest-feeds/prepare-article";
import { fixtureInput, writeRows, commitFixtureFiles, readWritten, compactRows } from "./partition-fixtures";
import { fixtureGit } from "./publication-recordings";
import { stagePlannerHistory } from "../scripts/feed-ingest-plan-history";
import { source, context } from "./harvest-recordings";
import { sourceSnapshot } from "../src/harvest-feeds/load-harvest-inputs";
import { recordedPlan } from "./plan-recordings";
import { runFeedPlan } from "../src/run-feed-plan";
import { stageStore } from "../src/api/stage-store";
import { createPermittedFetcher } from "../src/harvest-feeds/robots-policy";

async function recording() {
  return z.object({
    selected: z.string(), selected_offer: z.string(), published: z.string(), published_offer: z.string(),
    unknown: z.string(), unknown_offer: z.string(), first_seen_at: z.string(),
  }).parse(await Bun.file(new URL("../../../tests/fixtures/feed-ingest-plan/article-identity-history.json", import.meta.url)).json());
}

test("direct legacy associations keep the earliest first sight and do not invent unknown query variants", async () => {
  const fixture = await recording();
  for (const tidy_urls of [true, false]) {
    const identities = new ArticleIdentityEvidence({ tidy_urls });
    const old = deriveLegacyArticleIdentity(fixture.selected);
    const current = identities.remember(fixture.selected);
    expect(identities.keysFor(current.url_key)).toContain(old.url_key);
    const earlier = DiscoveredArticleRowSchema.parse({
      url_key: old.url_key, first_seen_at: fixture.first_seen_at, date: fixture.first_seen_at.slice(0, 10),
    });
    const later = DiscoveredArticleRowSchema.parse({
      url_key: current.url_key, first_seen_at: "2026-10-21T09:00:00Z", date: "2026-10-21",
    });
    expect(identities.discoveries([earlier, later]).find(row => row.url_key === current.url_key))
      .toEqual({ ...earlier, url_key: current.url_key });
    expect(earlier.url_key).toBe(old.url_key);
    const unknown = identities.remember(fixture.unknown_offer);
    expect(identities.keysFor(unknown.url_key)).not.toContain(deriveLegacyArticleIdentity(fixture.unknown).url_key);
    expect(() => identities.remember(fixture.selected, "f".repeat(64))).toThrow("recorded key");
  }
});

test("native selected metadata and an actual published item recover older keys without rewriting them", async () => {
  const root = await mkdtemp(join(tmpdir(), "article-identity-history-"));
  try {
    const fixture = await recording();
    const held = await fixtureInput(root, { count: 1 });
    held.inputs.harvest.config.discovered_articles.lookback_days = 2;
    held.inputs.clock_config.collect.published_window_days = 2;
    const oldSelected = deriveLegacyArticleIdentity(fixture.selected);
    const selected = { ...selectedArticleMetadata(held.curation.articles[0]!),
      canonical_url: oldSelected.canonical_url, url_key: oldSelected.url_key,
      run_id: held.context.run_id, attempt: 2, date: held.context.date };
    const stateRoot = join(root, "state");
    const written = await writeRows(stateRoot, "selected-articles", selected.date,
      { ...SelectedArticleRowContract, schemaVersion: LEGACY_SELECTED_ARTICLE_VERSION }, [selected]);
    const digestPath = `frontend/public/digest/${selected.date.replaceAll("-", "/")}/digest.json`;
    await mkdir(join(root, "frontend", "public", "digest", ...selected.date.split("-")), { recursive: true });
    await writeFile(join(root, digestPath), JSON.stringify({
      date: selected.date, generated_at: held.context.now,
      runs: [{ n: 1, run_id: held.context.run_id, items_added: 1 }],
      items: [{ item_id: "published-01", source_id: "recorded-news", source_url: fixture.published, introduced_by_run: 1 }],
    }));
    await commitFixtureFiles(root, [...written.files.map(file => `state/${file.path}`), digestPath]);
    await compactRows(stateRoot, "selected-articles", selected.date, SelectedArticleRowContract, [selected], "daily", root);
    await fixtureGit(root, ["sparse-checkout", "init", "--no-cone"]);
    const staged = await stagePlannerHistory(root, held.inputs, held.context.now);
    expect(staged.selected_days.map(day => day.day)).toContain("2026-10-20");
    held.inputs.settings.inputs.selected_days = staged.selected_days;
    const publishedKey = deriveLegacyArticleIdentity(fixture.published).url_key;
    const rows = [DiscoveredArticleRowSchema.parse({
      url_key: oldSelected.url_key, first_seen_at: fixture.first_seen_at, date: fixture.first_seen_at.slice(0, 10),
    })];
    const identities = await readArticleIdentityHistory(held.inputs, held.context.now, rows, [{
      version: "2026-09-12T18:40", url_key: publishedKey, published_on: selected.date, item_id: "published-01",
    }]);
    const selectedNow = identities.remember(fixture.selected_offer);
    const publishedNow = identities.remember(fixture.published_offer);
    expect(identities.keysFor(selectedNow.url_key)).toContain(oldSelected.url_key);
    expect(identities.keysFor(publishedNow.url_key)).toContain(publishedKey);
    const saved = await rememberDiscoveries(rows, identities.discoveries(rows), held.context, {
      outputRoot: root, registryEntry: held.inputs.registrations.discovered_articles, ledgerSettings: held.inputs.ledgerSettings,
    });
    const oldDay = await readWritten(root, "discovered-articles", rows[0]!.date, DiscoveredArticleRowContract, saved.result);
    expect(oldDay.rows.find(row => row.url_key === selectedNow.url_key)?.first_seen_at).toBe(fixture.first_seen_at);
    const reread = await readWritten(stateRoot, "selected-articles", selected.date, SelectedArticleRowContract, written);
    expect(reread.rows[0]).toMatchObject({ canonical_url: oldSelected.canonical_url, url_key: oldSelected.url_key });
    const prepared = prepareArticle({
      source: sourceSnapshot(held.inputs.harvest, source()),
      entry: { entry_ordinal: 0, link: fixture.published_offer, title: "Published story",
        categories: [], author: null, published_at: null, media_types: [] },
    }, held.inputs.harvest, { ...context(), identities,
      exclusions: { published_on: new Map([[publishedKey, selected.date]]), settled_failure_codes: new Map(), published_window_days: 2 } });
    expect(prepared.status).toBe("rejected");
    if (prepared.status === "rejected") expect(prepared.result.rejection).toMatchObject({
      drop_reason: "ALREADY_PUBLISHED", details: { matched_url_key: publishedKey },
    });
    await writeFile(join(root, digestPath), "{}");
    const gap = await readArticleIdentityHistory(held.inputs, held.context.now, [], [{
      version: "2026-09-12T18:40", url_key: publishedKey, published_on: selected.date, item_id: "published-01",
    }]);
    expect(gap.complete).toBe(false);
    expect(gap.keysFor(gap.remember(fixture.published_offer).url_key)).not.toContain(publishedKey);
  } finally { await rm(root, { recursive: true, force: true }); }
}, 60_000);

test("wrapper aliases cannot transfer exclusions between distinct destinations", async () => {
  const fixture = z.object({ allowed: z.array(z.object({ offered: z.string() })) }).parse(await Bun.file(new URL(
    "../../../tests/fixtures/feed-ingest-plan/harvest-url-cleanup.json", import.meta.url,
  )).json());
  const wrapper = fixture.allowed[1]!.offered;
  const identities = new ArticleIdentityEvidence({ tidy_urls: true });
  const left = identities.remember(wrapper);
  const right = identities.remember(wrapper.replace("second", "other"));
  expect(left.url_key).not.toBe(right.url_key);
  const wrapperKey = deriveArticleIdentity(wrapper, { tidy_urls: false }).url_key;
  expect(identities.keysFor(left.url_key)).not.toContain(wrapperKey);
  expect(identities.keysFor(right.url_key)).not.toContain(wrapperKey);
  const unsafe = z.object({ refused: z.array(z.object({ offered: z.string() })) }).parse(await Bun.file(new URL(
    "../../../tests/fixtures/feed-ingest-plan/harvest-url-cleanup.json", import.meta.url,
  )).json()).refused[0]!.offered;
  const disabled = new ArticleIdentityEvidence({ tidy_urls: false });
  expect(disabled.remember(unsafe).canonical_url).toBe(deriveArticleIdentity(unsafe, { tidy_urls: false }).canonical_url);
  expect(disabled.complete).toBe(false);
  const plain = deriveArticleIdentity("https://news.example/story?id=1#part", { tidy_urls: false });
  expect(plain.canonical_url).toBe("https://news.example/story");
  expect(disabled.remember("https://news.example/story?discard=%0A").canonical_url).toBe(plain.canonical_url);
});

test("query variants retain their offer ordinals and downloads but produce only one selected key", async () => {
  const held = await recordedPlan();
  try {
    held.transport.recordings.bodies.rss = held.transport.recordings.bodies.rss.replace(
      "<link>https://news.example/second</link>",
      "<link>https://news.example/story/?edition=other#part</link>",
    );
    const result = await runFeedPlan({ article_limit: 2 }, held.inputs, held.runtime);
    expect(result.row.status).toBe("completed");
    const batch = stageStore(held.inputs).read("parsed", result.batches.parsed_batch_id!, ParsedFeedBatchSchema);
    expect(batch.candidates.map(candidate => candidate.entry_ordinal)).toEqual([0, 2]);
    expect(batch.offers.map(offer => offer.entry.entry_ordinal)).toEqual([0, 2]);
    expect(new Set(batch.candidates.map(candidate => candidate.url_key)).size).toBe(1);
    expect(result.selected).toHaveLength(1);
    expect(held.transport.requests.filter(request => request.url.pathname === "/story/")).toHaveLength(2);
  } finally { await held.close(); }
});

test("accepted schemes retain query evidence and oversized serialized addresses cannot abort a plan or dispatch", async () => {
  const held = await recordedPlan();
  try {
    const fixture = z.object({
      mixed_scheme_offer: z.string(), expanded_path_character: z.string(), expanded_path_repetitions: z.number(),
    }).parse(await Bun.file(new URL(
      "../../../tests/fixtures/feed-ingest-plan/article-identity-history.json", import.meta.url,
    )).json());
    const expanded = `https://news.example/${fixture.expanded_path_character.repeat(fixture.expanded_path_repetitions)}`;
    expect(expanded).toHaveLength(251);
    expect(new URL(expanded).href).toHaveLength(2091);
    held.inputs.harvest.config.harvest.tidy_urls = false;
    expect(() => deriveArticleIdentity(expanded, held.inputs.harvest.config.harvest)).toThrow("serialized article address");
    const fetcher = createPermittedFetcher(held.inputs.harvest.config.harvest, held.inputs.harvest.extraction, held.runtime.boundary);
    expect(await fetcher.fetch(expanded)).toMatchObject({ failure: "unsafe-target" });
    expect(held.transport.requests).toHaveLength(0);
    held.transport.recordings.responses["https://news.example/feed.xml"] = [{
      status: 200, body: `<rss version="2.0"><channel><title>Recorded URL bounds</title>
        <item><title>Accepted offer</title><link>${fixture.mixed_scheme_offer}</link></item>
        <item><title>Oversized address</title><link>${expanded}</link></item></channel></rss>`,
    }];
    const result = await runFeedPlan({ article_limit: 2 }, held.inputs, held.runtime);
    expect(result.row.status).toBe("completed");
    const batch = stageStore(held.inputs).read("parsed", result.batches.parsed_batch_id!, ParsedFeedBatchSchema);
    expect(batch.offers.map(offer => offer.entry.link)).toEqual([
      fixture.mixed_scheme_offer.replace(/^HTTPS:/, "https:"),
    ]);
    expect(batch.candidates.map(candidate => candidate.canonical_url)).toEqual(["https://news.example/second"]);
    expect(result.selected).toHaveLength(1);
    expect(held.transport.requests.some(request => request.url.href === new URL(expanded).href)).toBe(false);
    expect(held.transport.requests.filter(request => request.url.pathname === "/second")).toHaveLength(1);
  } finally { await held.close(); }
});
