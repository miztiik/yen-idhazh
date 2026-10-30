/** Keep cleaned URLs as the sole article identity and preserve current-key deduplication. */
import { expect, test } from "bun:test";
import { ParsedFeedBatchSchema } from "@idhazh/common-contracts";
import { deriveArticleIdentity } from "../src/harvest-feeds/article-identity";
import { createPermittedFetcher } from "../src/harvest-feeds/robots-policy";
import { stageStore } from "../src/api/stage-store";
import { recordedPlan } from "./plan-recordings";
import { runFeedPlan } from "../src/run-feed-plan";

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

test("scheme cleanup retains accepted offers while an oversized cleaned address is refused", async () => {
  const held = await recordedPlan();
  try {
    const mixedSchemeOffer = "HTTPS://news.example/second?edition=old#part";
    const expanded = `https://news.example/${String.fromCodePoint(0x0b85).repeat(230)}`;
    expect(expanded).toHaveLength(251);
    expect(new URL(expanded).href).toHaveLength(2091);
    held.inputs.harvest.config.harvest.tidy_urls = false;
    expect(() => deriveArticleIdentity(expanded, held.inputs.harvest.config.harvest)).toThrow("serialized article address");
    const fetcher = createPermittedFetcher(
      held.inputs.harvest.config.harvest, held.inputs.harvest.extraction, held.runtime.boundary,
    );
    expect(await fetcher.fetch(expanded)).toMatchObject({ failure: "unsafe-target" });
    expect(held.transport.requests).toHaveLength(0);
    held.transport.recordings.responses["https://news.example/feed.xml"] = [{
      status: 200, body: `<rss version="2.0"><channel><title>Recorded URL bounds</title>
        <item><title>Accepted offer</title><link>${mixedSchemeOffer}</link></item>
        <item><title>Oversized address</title><link>${expanded}</link></item></channel></rss>`,
    }];
    const result = await runFeedPlan({ article_limit: 2 }, held.inputs, held.runtime);
    expect(result.row.status).toBe("completed");
    const batch = stageStore(held.inputs).read("parsed", result.batches.parsed_batch_id!, ParsedFeedBatchSchema);
    expect(batch.offers.map(offer => offer.entry.link)).toEqual([
      mixedSchemeOffer.replace(/^HTTPS:/, "https:"),
    ]);
    expect(batch.candidates.map(candidate => candidate.canonical_url)).toEqual(["https://news.example/second"]);
    expect(result.selected).toHaveLength(1);
    expect(held.transport.requests.some(request => request.url.href === new URL(expanded).href)).toBe(false);
    expect(held.transport.requests.filter(request => request.url.pathname === "/second")).toHaveLength(1);
  } finally { await held.close(); }
});
