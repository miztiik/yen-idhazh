/** Preserve resource URL bytes while keeping same-address deduplication and refusal bounds. */
import { expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { deriveArticleIdentity } from "../src/harvest-feeds/article-identity";
import { deriveFeedIdentity } from "../src/harvest-feeds/feed-identity";
import { createSourceFetcher } from "../src/harvest-feeds/fetch-source";
import { recordedPlan } from "./plan-recordings";
import { collectRecordedFeeds } from "./collection-recordings";
import { executeSelection } from "../src/api/selection-operation";
import { operationLink } from "../src/api/operation-context";
import { readUrlProtocol } from "./harvest-recordings";

test("article and feed-document normalization preserves the declared resource distinctions and is idempotent", async () => {
  const fixture = await readUrlProtocol();
  for (const derive of [deriveArticleIdentity, deriveFeedIdentity]) {
    for (const vector of fixture.normalization) {
      const identity = derive(vector.offered);
      expect(identity.canonical_url, vector.offered).toBe(vector.canonical_url);
      expect(identity.url_key).toBe(createHash("sha256").update(vector.canonical_url, "utf8").digest("hex"));
      expect(derive(identity.canonical_url)).toEqual(identity);
    }
    for (const addresses of fixture.distinct) {
      const identities = addresses.map(address => derive(address));
      expect(new Set(identities.map(identity => identity.canonical_url)).size).toBe(addresses.length);
      expect(new Set(identities.map(identity => identity.url_key)).size).toBe(addresses.length);
    }
    const prefix = "https://news.example/";
    const maximum = `${prefix}${"a".repeat(2048 - prefix.length)}`;
    expect(derive(maximum).canonical_url).toBe(maximum);
    for (const address of [maximum + "a", maximum + "#", "not-a-url", "https://[invalid-host/", "ftp://news.example/story"]) {
      expect(() => derive(address)).toThrow();
    }
  }
});

test("distinct query resources retain their ordinals and downloads while repeated addresses select once", async () => {
  const held = await recordedPlan();
  try {
    held.transport.recordings.bodies.rss = held.transport.recordings.bodies.rss.replace(
      "<link>https://news.example/second</link>",
      "<link>https://news.example/story/?edition=other#part</link>",
    ).replace("</channel>", `<item><title>Repeated resource</title>
      <link>https://news.example/story/?utm_source=feed&amp;b=2&amp;a=1#other</link></item></channel>`);
    const { batch } = await collectRecordedFeeds(held.inputs, held.runtime);
    expect(batch.candidates.map(candidate => candidate.entry_ordinal)).toEqual([0, 2, 3]);
    expect(batch.offers.map(offer => offer.entry.entry_ordinal)).toEqual([0, 2, 3]);
    expect(new Set(batch.candidates.map(candidate => candidate.url_key)).size).toBe(2);
    expect((await executeSelection({ links: [operationLink(batch)] }, held.inputs, held.runtime)).batch.articles).toHaveLength(2);
    expect(held.transport.requests.filter(request => request.url.pathname === "/story/").map(request => request.url.href)).toEqual([
      "https://news.example/story/?utm_source=feed&b=2&a=1",
      "https://news.example/story/?edition=other",
      "https://news.example/story/?utm_source=feed&b=2&a=1",
    ]);
  } finally { await held.close(); }
});

test("scheme normalization retains accepted offers while an oversized serialized address is refused", async () => {
  const held = await recordedPlan();
  try {
    const mixedSchemeOffer = "HTTPS://news.example/second?edition=old#part";
    const expanded = `https://news.example/${String.fromCodePoint(0x0b85).repeat(230)}`;
    expect(expanded).toHaveLength(251);
    expect(new URL(expanded).href).toHaveLength(2091);
    expect(() => deriveArticleIdentity(expanded)).toThrow("serialized resource address");
    expect(() => deriveFeedIdentity(expanded)).toThrow("serialized resource address");
    const fetcher = createSourceFetcher(
      held.inputs.harvest.config.harvest, held.inputs.harvest.extraction, held.runtime.boundary,
    );
    try {
      for (const kind of ["article", "feed"] as const) {
        expect(await fetcher.fetch(expanded, undefined, kind)).toMatchObject({ failure: "unsafe-target" });
      }
      expect(held.transport.requests).toHaveLength(0);
    } finally { await fetcher.close(); }
    held.transport.recordings.responses["https://news.example/feed.xml"] = [{
      status: 200, body: `<rss version="2.0"><channel><title>Recorded URL bounds</title>
        <item><title>Accepted offer</title><link>${mixedSchemeOffer}</link></item>
        <item><title>Oversized address</title><link>${expanded}</link></item></channel></rss>`,
    }];
    const { batch } = await collectRecordedFeeds(held.inputs, held.runtime);
    expect(batch.offers.map(offer => offer.entry.link)).toEqual([
      mixedSchemeOffer.replace(/^HTTPS:/, "https:"),
    ]);
    expect(batch.candidates.map(candidate => candidate.canonical_url)).toEqual(["https://news.example/second?edition=old"]);
    expect(held.transport.requests.some(request => request.url.href === new URL(expanded).href)).toBe(false);
    expect(held.transport.requests.filter(request => request.url.pathname === "/second")).toHaveLength(1);
  } finally { await held.close(); }
});
