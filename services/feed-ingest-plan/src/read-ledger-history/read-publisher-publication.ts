/** Which actual publications today have an unambiguous recorded publisher identity? */
import { EditorialSelectionContract } from "@idhazh/common-contracts";
import type { LedgerRegistration } from "@idhazh/ledger-file-writer";
import type { SeenDayInput } from "../config/service-settings";
import { ItemHealthPublicationSchema } from "../metrics/publication-evidence";
import { defaultDayInput, historyCoverage, readNamedDays, usableDay } from "./named-days";
import { PublishedRowProjectionContract } from "./published-row";
import { ITEM_HEALTH_ROW_SCHEMA_VERSION } from "./item-health-version";
import type { PublisherPublicationHistory } from "../curate-article-portfolio/publisher-exposure";
import { writeJsonLine } from "../logging/structured-logger";
import { classifyPublicationHistoryError } from "./classify-publication-history-error";
import { LedgerHistoryReadError } from "./ledger-history-error";

type PublisherPublicationInput = Readonly<{
  root: string; day: string;
  published: LedgerRegistration; item_health: LedgerRegistration; selections: LedgerRegistration;
  published_days: readonly SeenDayInput[]; health_days: readonly SeenDayInput[];
}>;

async function readConfirmedPublication(input: PublisherPublicationInput) {
  const named = (days: readonly SeenDayInput[], registration: LedgerRegistration) => {
    const today = days.filter(day => day.day === input.day);
    if (today.length > 1) throw new Error("Publisher publication history repeats its UTC day");
    return today.length === 0 ? [defaultDayInput(registration.prefix, input.day)] : today;
  };
  const published = await readNamedDays(input.root, input.published,
    named(input.published_days, input.published), PublishedRowProjectionContract);
  const counts = new Map<string, number>();
  const gaps: string[] = [];
  if (!published.every(usableDay)) gaps.push("publication_history_unavailable");
  const publications = new Map<string, string>();
  for (const day of published) for (const { row } of day.rows) {
    if (row.published_on !== input.day) throw new LedgerHistoryReadError("Publication row differs from its named UTC day");
    const prior = publications.get(row.url_key);
    if (prior !== undefined && prior !== row.item_id) gaps.push("conflicting_publication_identity");
    publications.set(row.url_key, row.item_id);
  }
  let identityHistory: ReturnType<typeof historyCoverage> | null = null;
  let healthHistory: ReturnType<typeof historyCoverage> | null = null;
  if (publications.size > 0) {
    const [health, selections] = await Promise.all([
      readNamedDays(input.root, input.item_health, named(input.health_days, input.item_health), {
        schema: ItemHealthPublicationSchema, schemaVersion: ITEM_HEALTH_ROW_SCHEMA_VERSION,
        projectedFields: ["date", "run_id", "item_id", "url_key", "source_id", "stage", "outcome"],
      }),
      readNamedDays(input.root, input.selections,
        [defaultDayInput(input.selections.prefix, input.day)], EditorialSelectionContract),
    ]);
    identityHistory = historyCoverage(selections);
    healthHistory = historyCoverage(health);
    if (!health.every(usableDay) || !selections.every(usableDay)) gaps.push("publication_identity_history_unavailable");
    for (const day of health) for (const { row } of day.rows) {
      if (row.date !== input.day) throw new LedgerHistoryReadError("Publication health differs from its named UTC day");
    }
    for (const day of selections) for (const { row } of day.rows) {
      if (row.date !== input.day) throw new LedgerHistoryReadError("Publisher snapshot differs from its named UTC day");
    }
    for (const [url, item] of publications) {
      const owners = new Map(health.flatMap(day => day.rows).filter(({ row }) =>
        row.item_id === item && row.url_key === url && row.stage === "publish" && row.outcome === "ok")
        .map(({ row }) => [JSON.stringify([row.run_id, row.source_id]), row]));
      if (owners.size !== 1) { gaps.push("publication_owner_unavailable"); continue; }
      const owner = [...owners.values()][0]!;
      const snapshots = selections.flatMap(day => day.rows).filter(({ row, identity }) =>
        row.url_key === url && row.source_id === owner.source_id && identity.run_id === owner.run_id);
      const publishers = new Set(snapshots.map(({ row }) => row.source.publisher_id));
      const publisher = publishers.size === 1 ? [...publishers][0] : null;
      if (publisher === null || publisher === undefined) { gaps.push("recorded_publisher_unavailable"); continue; }
      counts.set(publisher, (counts.get(publisher) ?? 0) + 1);
    }
  }
  const evidence: PublisherPublicationHistory = {
    day: input.day, availability: gaps.length === 0 ? "available" : "unavailable", counts,
  };
  return {
    ...evidence, gaps: [...new Set(gaps)],
    history: { publications: historyCoverage(published), health: healthHistory, identities: identityHistory },
  };
}

export async function readPublisherPublication(input: PublisherPublicationInput) {
  try {
    return await readConfirmedPublication(input);
  } catch (error) {
    const diagnostic = classifyPublicationHistoryError(error);
    if (diagnostic === null) throw error;
    const gap = "invalid_publication_history";
    writeJsonLine({
      timestamp: new Date().toISOString(), level: "WARN", event: "publisher_history_unavailable",
      day: input.day, gap, diagnostic,
    });
    const evidence: PublisherPublicationHistory = {
      day: input.day, availability: "unavailable", counts: new Map(),
    };
    return {
      ...evidence, gaps: [gap],
      history: { publications: historyCoverage([]), health: null, identities: null },
    };
  }
}
