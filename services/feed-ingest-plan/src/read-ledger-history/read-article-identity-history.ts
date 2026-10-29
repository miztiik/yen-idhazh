/** Recover article addresses from bounded selected days and actually published day items. */
import { SelectedArticleRowContract } from "@idhazh/common-contracts";
import type { DiscoveredArticleRow } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import { requiredUtcDays } from "../utc-instant";
import { readPlannerDay, createPlannerHistoryCache } from "./read-planner-history";
import { defaultDayInput } from "./named-days";
import { readNamedGitFile, fixedHistoryRevision } from "./raw-day-members";
import { DigestPublicationSchema } from "../metrics/publication-evidence";
import type { PublishedRow } from "../metrics/publication-evidence";
import { ArticleIdentityEvidence } from "./article-identity-evidence";
import { mapPool } from "../harvest-feeds/harvest-pool";
import { classifyPlannerHistoryGap } from "./planner-history-gap";
import { InvalidArticleUrlError } from "../harvest-feeds/legacy-article-identity";
import { UnsafeTargetError } from "../harvest-feeds/safe-target";
import { LedgerHistoryReadError } from "./ledger-history-error";
import { z } from "zod";

export function articleIdentityDays(inputs: PlanInputs, now: string, discoveries: readonly DiscoveredArticleRow[] = []) {
  return [...new Set([
    ...requiredUtcDays(now, inputs.harvest.config.discovered_articles.lookback_days),
    ...requiredUtcDays(now, inputs.clock_config.collect.published_window_days),
    now.slice(0, 10), ...discoveries.map(row => row.date),
  ])].sort();
}

export async function readArticleIdentityHistory(
  inputs: PlanInputs, now: string, discoveries: readonly DiscoveredArticleRow[], published: readonly PublishedRow[],
) {
  const identities = new ArticleIdentityEvidence(inputs.harvest.config.harvest);
  const cache = createPlannerHistoryCache<import("@idhazh/common-contracts").SelectedArticleRow>();
  const selected = inputs.settings.inputs.selected_days;
  const gap = (day: string, source: string, reason: string) => {
    identities.complete = false;
    console.error(JSON.stringify({ event: "article_identity_history_gap", day, source, reason }));
  };
  let revision: string;
  try { revision = selected[0]?.raw_revision ?? await fixedHistoryRevision(inputs.root); }
  catch (error) {
    if (classifyPlannerHistoryGap(error) === null) throw error;
    gap(now.slice(0, 10), "selected-articles", "unavailable-revision");
    return identities;
  }
  function remember(address: string, key: string, day: string, source: string) {
    try { identities.remember(address, key); }
    catch (error) {
      if (!(error instanceof InvalidArticleUrlError || error instanceof UnsafeTargetError
        || error instanceof LedgerHistoryReadError)) throw error;
      gap(day, source, "invalid-address-association");
    }
  }
  await mapPool(articleIdentityDays(inputs, now, discoveries), inputs.harvest.config.harvest.concurrency, async day => {
    const named = selected.filter(input => input.day === day);
    if (named.length > 1) throw new LedgerHistoryReadError("Selected identity history repeats its UTC day");
    if (named[0]?.raw_revision !== undefined && named[0].raw_revision !== revision) {
      throw new LedgerHistoryReadError("Selected identity history mixes Git revisions");
    }
    const held = await readPlannerDay(inputs.root, inputs.registrations.selected_articles,
      named[0] ?? { ...defaultDayInput(inputs.registrations.selected_articles.prefix, day), raw_revision: revision },
      SelectedArticleRowContract, cache);
    for (const row of held.rows) remember(row.canonical_url, row.url_key, day, "selected-articles");
    if (!held.complete) gap(day, "selected-articles", "incomplete-day");
  });
  const byDay = Map.groupBy(published, row => row.published_on);
  await mapPool([...byDay], inputs.harvest.config.harvest.concurrency, async ([day, rows]) => {
    const path = `${inputs.settings.inputs.digest_root}/${day.replaceAll("-", "/")}/digest.json`;
    try {
      const content = await readNamedGitFile(inputs.root, path, revision);
      if (content === undefined) { gap(day, "published-digest", "missing-day"); return; }
      const digest = DigestPublicationSchema.parse(JSON.parse(content));
      if (digest.date !== day) throw new LedgerHistoryReadError("Published digest differs from its named UTC day");
      const items = new Map(digest.items.map(item => [item.item_id, item]));
      for (const row of rows) {
        const item = items.get(row.item_id);
        if (item === undefined) gap(day, "published-digest", "missing-item");
        else remember(item.source_url, row.url_key, day, "published-digest");
      }
    } catch (error) {
      if (error instanceof SyntaxError || error instanceof z.ZodError || classifyPlannerHistoryGap(error) !== null) {
        gap(day, "published-digest", "invalid-day"); return;
      }
      throw error;
    }
  });
  return identities;
}
