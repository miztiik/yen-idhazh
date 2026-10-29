/** Associate recoverable saved addresses with current keys without relabeling historical rows. */
import type { DiscoveredArticleRow } from "@idhazh/common-contracts";
import { deriveUrlKey } from "@idhazh/common-contracts";
import { deriveArticleIdentity } from "../harvest-feeds/article-identity";
import type { ArticleUrlPolicy } from "../harvest-feeds/article-url";
import { deriveLegacyArticleIdentity, InvalidArticleUrlError } from "../harvest-feeds/legacy-article-identity";
import { UnsafeTargetError } from "../harvest-feeds/safe-target";
import { LedgerHistoryReadError } from "./ledger-history-error";

export class ArticleIdentityEvidence {
  private readonly canonical = new Map<string, string>();
  private readonly destinations = new Map<string, Set<string>>();
  private readonly sources = new Map<string, Set<string>>();
  private readonly ambiguous = new Set<string>();
  complete = true;

  constructor(private readonly policy: ArticleUrlPolicy) {}

  remember(address: string, storedKey?: string) {
    const current = deriveArticleIdentity(address, this.policy);
    const identities = [current];
    try { identities.push(deriveLegacyArticleIdentity(address)); }
    catch (error) {
      if (!(error instanceof InvalidArticleUrlError)) throw error;
      this.complete = false;
      console.error(JSON.stringify({ event: "article_identity_history_gap", reason: "invalid-legacy-address" }));
    }
    try { identities.push(deriveArticleIdentity(address, { tidy_urls: !this.policy.tidy_urls })); }
    catch (error) {
      if (!(error instanceof InvalidArticleUrlError || error instanceof UnsafeTargetError)) throw error;
      this.complete = false;
      console.error(JSON.stringify({ event: "article_identity_history_gap", reason: "unsafe-alternate-policy" }));
    }
    const keys = new Set([...identities.map(identity => identity.url_key), deriveUrlKey(address)]);
    if (storedKey !== undefined && !keys.has(storedKey)) {
      throw new LedgerHistoryReadError("Saved article address does not establish its recorded key");
    }
    for (const identity of identities) {
      const prior = this.canonical.get(identity.url_key);
      if (prior !== undefined && prior !== identity.canonical_url) {
        throw new LedgerHistoryReadError("Article hash has conflicting canonical addresses");
      }
      this.canonical.set(identity.url_key, identity.canonical_url);
    }
    const sources = this.sources.get(current.url_key) ?? new Set<string>();
    for (const key of keys) {
      const destinations = this.destinations.get(key) ?? new Set<string>();
      destinations.add(current.url_key);
      this.destinations.set(key, destinations);
      if (destinations.size > 1 && !this.ambiguous.has(key)) {
        this.ambiguous.add(key);
        this.complete = false;
        console.error(JSON.stringify({ event: "article_identity_history_gap", reason: "ambiguous-key" }));
      }
      sources.add(key);
    }
    this.sources.set(current.url_key, sources);
    return current;
  }

  keysFor(key: string): readonly string[] {
    return [...new Set([key, ...[...(this.sources.get(key) ?? [])].filter(source => !this.ambiguous.has(source))])];
  }

  discoveries(rows: readonly DiscoveredArticleRow[]): DiscoveredArticleRow[] {
    const saved = new Map<string, DiscoveredArticleRow>();
    for (const row of rows) {
      const previous = saved.get(row.url_key);
      if (previous === undefined || row.first_seen_at < previous.first_seen_at) saved.set(row.url_key, row);
    }
    const byKey = new Map(saved);
    for (const key of this.sources.keys()) {
      let first: DiscoveredArticleRow | undefined;
      for (const source of this.keysFor(key)) {
        const row = saved.get(source);
        if (row !== undefined && (first === undefined || row.first_seen_at < first.first_seen_at)) first = row;
      }
      if (first !== undefined) byKey.set(key, { ...first, url_key: key });
    }
    return [...byKey.values()];
  }
}
