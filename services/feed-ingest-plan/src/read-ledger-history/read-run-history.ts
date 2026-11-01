/** Load the saved evidence one execution will reuse without reopening historical files. */
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { readStoredPlannerParquet, readPlannerDayFiles, regularPlannerPath, rawDayDirectory } from "@idhazh/ledger-file-writer";
import type { FeedHealthStateRow } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { RunContext } from "../resolve-run-context";
import { sourceSnapshot } from "../harvest-feeds/load-harvest-inputs";
import { plannerMemory } from "../planner-memory";
import { createStageLogger } from "../logging/structured-logger";
import { readFeedHistory, validateHealthDayInputs } from "./read-feed-history";
import { readHealthCapture } from "./read-health-capture";
import { createPlannerHistoryCache } from "./read-planner-history";
import { readDiscoveredEvidence } from "./read-discovered-evidence";
import { readExclusionEvidence } from "./read-exclusion-evidence";
import { readPublisherPublication } from "./read-publisher-publication";
import { resolveHealthDays } from "./resolve-health-days";
import { closedRequestDays } from "./request-summary";
import { defaultDayInput } from "./named-days";
import { LedgerHistoryReadError } from "./ledger-history-error";
import { requiredUtcDays } from "../utc-instant";

export type CurrentHealthWork = { context: RunContext; rows: readonly FeedHealthStateRow[] };
export function healthHistoryInput(inputs: PlanInputs, now: string, current?: CurrentHealthWork) {
  return {
    root: inputs.root, now, sources: inputs.harvest.sources.map(source => sourceSnapshot(inputs.harvest, source)),
    policy: inputs.clock_config.collect, ...inputs.harvest.config.feedback,
    lifecycle_policy: inputs.harvest.config.availability,
    concurrency: inputs.harvest.config.harvest.concurrency, health: inputs.registrations.feed_health_state,
    health_days: inputs.settings.inputs.feed_health_days,
    own_rows: structuredClone(plannerMemory(inputs).health()),
    ...(current === undefined ? {} : {
      current_rows: current.rows, exclude_execution: { run_id: current.context.run_id, attempt: current.context.writer.attempt },
      log: createStageLogger(current.context),
    }),
  };
}

async function readHistoryJson(root: string, path: string) {
  try { return JSON.parse(await readFile(await regularPlannerPath(root, path), "utf8")) as unknown; }
  catch (error) {
    if (error instanceof Error && "code" in error && error.code === "ENOENT") return undefined;
    if (error instanceof SyntaxError) throw new LedgerHistoryReadError("Invalid named history JSON", { cause: error });
    throw error;
  }
}

export async function readPlanningHistory(
  inputs: PlanInputs, now: string, current?: CurrentHealthWork,
  cache = createPlannerHistoryCache<Record<string, unknown>>(),
) {
  const input = healthHistoryInput(inputs, now, current);
  validateHealthDayInputs(input);
  const inventory = await resolveHealthDays({
    ledger: "feed-health-state", prefix: input.health.prefix, now,
    health_window_days: Math.max(input.lifecycle_window_days, input.policy.reliability_window_days) + 1,
    request_report_closed_days: input.request_report_closed_days,
    period_limit: inputs.settings.inputs.health_period_limit, authored: input.health_days,
    read: path => readHistoryJson(inputs.root, path),
    read_period: path => {
      const local = resolve(inputs.root, path);
      const key = `stored:${local}`;
      // A declared period is a required file, even when its local path is missing.
      cache.compact.set(path, Promise.resolve(path));
      let pending = cache.files.get(key);
      if (pending === undefined) {
        pending = regularPlannerPath(inputs.root, path)
          .then(() => readStoredPlannerParquet(local, "feed-health-state"));
        cache.files.set(key, pending);
      }
      return pending;
    },
    raw_files: async day => {
      const directory = rawDayDirectory(input.health, day);
      let pending = cache.days.get(directory);
      if (pending === undefined) {
        pending = readPlannerDayFiles(inputs.root, input.health, day);
        cache.days.set(directory, pending);
      }
      return (await pending).members;
    },
  });
  for (const notice of inventory.notices) input.log?.("history", "failed", {
    source: "health-inventory", failed_check: "represented-day-read", reason: notice,
  });
  const health_days = inventory.inputs.map(({ day, raw_files }) => ({ day, raw_files: raw_files ?? [] }));
  const history = await readFeedHistory({ ...input, health_days, current_rows: [] }, cache);
  return { ...history, input_gap: inputs.settings.inputs.feed_health_input_gap
    || inventory.notices.some(notice => notice.startsWith("health_")) };
}

export async function readRunHistory(inputs: PlanInputs, context: RunContext) {
  const now = context.now;
  const current = { context, rows: [] };
  const cache = createPlannerHistoryCache<Record<string, unknown>>();
  const healthInput = healthHistoryInput(inputs, now, current);
  const tomorrow = new Date(`${now.slice(0, 10)}T00:00:00Z`);
  tomorrow.setUTCDate(tomorrow.getUTCDate() + 1);
  const dates = [now.slice(0, 10), tomorrow.toISOString().slice(0, 10)];
  const requestDays = [...new Set(dates.flatMap(day =>
    closedRequestDays(`${day}T00:00:00Z`, healthInput.request_report_closed_days)))].sort();
  const planning = readPlanningHistory(inputs, now, current, cache);
  const [health, requests, discovered, exclusions, publications] = await Promise.all([
    planning,
    planning.then(() => readHealthCapture({ ...healthInput, current_rows: [] }, requestDays.map(day =>
      healthInput.health_days.find(value => value.day === day) ?? defaultDayInput(healthInput.health.prefix, day)), cache)),
    readDiscoveredEvidence({
      root: inputs.root, now, registration: inputs.registrations.discovered_articles,
      discovered_files: inputs.settings.inputs.discovered_files, discovered_days: inputs.settings.inputs.discovered_days,
      lookback_days: inputs.harvest.config.discovered_articles.lookback_days,
      concurrency: inputs.harvest.config.harvest.concurrency,
      own_rows: structuredClone(plannerMemory(inputs).discoveries()), log: createStageLogger(context),
    }),
    Promise.all(dates.map(day => readExclusionEvidence({
      root: inputs.root, now: `${day}T00:00:00Z`,
      publishedWindowDays: inputs.clock_config.collect.published_window_days,
      settledFailureCodes: inputs.clock_config.collect.settled_failure_codes,
      publishedRegistration: inputs.registrations.published, itemHealthRegistration: inputs.registrations.item_health,
      publishedDays: inputs.settings.inputs.published_days.filter(value =>
        requiredUtcDays(`${day}T00:00:00Z`, inputs.clock_config.collect.published_window_days).includes(value.day)),
      settledFailureDays: inputs.settings.inputs.settled_failure_days.filter(value => value.day === day),
      concurrency: inputs.harvest.config.harvest.concurrency,
    }))),
    Promise.all(dates.map(day => readPublisherPublication({
      root: inputs.root, day, published: inputs.registrations.published, item_health: inputs.registrations.item_health,
      selections: inputs.registrations.selected_articles, published_days: inputs.settings.inputs.published_days,
      health_days: inputs.settings.inputs.settled_failure_days, log: createStageLogger(context),
    }))),
  ]);
  return {
    run_id: context.run_id, attempt: context.writer.attempt, health, requests, discovered,
    exclusions: new Map(dates.map((day, index) => [day, exclusions[index]!])),
    publications: new Map(dates.map((day, index) => [day, publications[index]!])),
  };
}
export type RunHistory = Awaited<ReturnType<typeof readRunHistory>>;
