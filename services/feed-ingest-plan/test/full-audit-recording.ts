/** Generate a bounded publication fixture from one real recorded planner attempt. */
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { CONTRACT_VERSION } from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import type { PersistLedgerResult } from "@idhazh/ledger-file-writer";
import type { FeedPlanResult } from "../src/run-feed-plan";
import type { PlanInputs } from "../src/load-plan-inputs";
import type { PlanningMetricsResult, PublicationRecorderInput } from "../src/metrics/metrics-recorder";
import { DigestPublicationSchema, PublishedRowSchema } from "../src/metrics/publication-evidence";
import { requiredHistoryDays, shiftUtcDay } from "../src/metrics/history-window";

export async function generatePublicationInput(
  plan: FeedPlanResult, metrics: PlanningMetricsResult, inputs: PlanInputs, root: string,
): Promise<PublicationRecorderInput> {
  await mkdir(root, { recursive: true });
  const date = plan.context.date;
  const asOf = `${shiftUtcDay(date, 1)}T00:00:00Z`;
  const digest = DigestPublicationSchema.parse({
    date, generated_at: plan.context.now,
    runs: [{ n: 1, run_id: plan.context.run_id, items_added: plan.evidence.partition.dispatches.length }],
    items: plan.evidence.partition.dispatches.map(({ content, selection }, index) => ({
      item_id: `fixture-${String(index + 1).padStart(2, "0")}`, source_id: selection.source_id,
      source_kind: selection.source.kind, source_url: content.canonical_url,
      source_name: selection.source.title, title: content.title, introduced_by_run: 1,
    })), leads: [],
  });
  const digestPath = join(root, "generated-digest.json");
  await writeFile(digestPath, JSON.stringify(digest));
  const published = await persistLedger({
    ledger: "published", outputRoot: root,
    registryEntry: { name: "published", family: "published", grain: "raw-and-compact",
      lifecycle_status: "active", prefix: ["published"] },
    writerContext: plan.context.writer, ledgerSettings: inputs.ledgerSettings,
    rowContract: { schema: PublishedRowSchema, schemaVersion: CONTRACT_VERSION },
    period: { tier: "raw", covers: date },
    rows: plan.evidence.partition.dispatches.map(({ content }, index) => PublishedRowSchema.parse({
      version: CONTRACT_VERSION, published_on: date, item_id: digest.items[index]!.item_id, url_key: content.url_key,
    })),
  });
  const paths = (day: string, files: readonly PersistLedgerResult[], outputRoot = inputs.outputRoot) => ({
    day, rawFiles: files.flatMap(result => result.files.map(file => join(outputRoot, ...file.path.split("/")))),
  });
  const days = requiredHistoryDays(asOf, inputs.harvest.config.metrics, date);
  return {
    run_id: plan.context.run_id, correlation_id: plan.context.correlation_id,
    as_of: asOf, through: date, config_sha256: plan.evidence.harvest.inputs.config_sha256,
    config: inputs.harvest.config.metrics, writer: { ...plan.context.writer, producer: "tests.generated-full-audit" },
    outputRoot: join(root, "observer"), ledgerSettings: inputs.ledgerSettings,
    registrations: { diversity: inputs.registrations.diversity, sources: inputs.registrations.source_runs },
    planning_days: days.map(day => {
      const empty = paths(day, []);
      return day === date ? {
        sources: paths(day, [metrics.files.source_runs]), ledgers: {
          "article-assessments": paths(day, [metrics.files.assessments]), diversity: paths(day, [metrics.files.diversity]),
          "editorial-selections": paths(day, [plan.files.selections]), dispatches: paths(day, [plan.files.dispatches]),
          rejections: paths(day, [plan.files.harvest_rejections, plan.files.screening_rejections, plan.files.curation_rejections]),
        },
      } : { sources: empty, ledgers: { "article-assessments": empty, diversity: empty,
        "editorial-selections": empty, dispatches: empty, rejections: empty } };
    }),
    publication_days: days.map(day => ({
      published: { ...paths(day, day === date ? [published] : [], root), schema_version: CONTRACT_VERSION },
      digest_path: day === date ? digestPath : null,
      health: { day, status: day === date && digest.items.length > 0 ? "rows" : "empty",
        rows: day !== date ? [] : digest.items.map((item, index) => ({
          date, run_id: plan.context.run_id, item_id: item.item_id, source_id: item.source_id,
          url_key: plan.evidence.partition.dispatches[index]!.content.url_key, stage: "publish" as const, outcome: "ok" as const,
        })) },
    })),
    event_pairs: [],
  };
}
