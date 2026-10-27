/** Stage only named native indexes and their bounded planner history files. */
import { resolve } from "node:path";
import {
  CompactIndexSchema, LedgerNameSchema, FeedHealthStateRowContract, RawDayIndexSchema, PlannerLedgerNameSchema,
} from "../../../packages/common-contracts/src/index";
import type { CompactIndex } from "../../../packages/common-contracts/src/index";
import type { PlanInputs } from "../src/load-plan-inputs";
import { mapPool } from "../src/harvest-feeds/harvest-pool";
import { requiredUtcDays } from "../src/utc-instant";
import { readPlannerParquet } from "../src/read-ledger-history/read-planner-parquet";
import { closedRequestDays } from "../src/read-ledger-history/health-summary";
import { completeHistoryDayInputs, createHistoryDayInputs, resolveHistoryIndexes, resolveHistoryInventory, sparseCheckoutPath } from "./feed-ingest-plan-outputs";
import { stageFeedHistory } from "./feed-ingest-plan-feed-history";
import { LedgerHistoryReadError } from "../src/read-ledger-history/ledger-history-error";
import { fixedHistoryRevision, listExactRawDayMembers, readNamedGitFile, verifyRawDayMember } from "../src/read-ledger-history/raw-day-members";

export async function stageNamedFiles(repository: string, paths: readonly string[]) {
  const names = [...new Set(paths)].map(sparseCheckoutPath);
  if (names.length === 0) return;
  const child = Bun.spawn(["git", "sparse-checkout", "add", "--skip-checks", "--stdin"], {
    cwd: repository, stdin: "pipe", stdout: "pipe", stderr: "pipe",
  });
  child.stdin.write(`${names.join("\n")}\n`);
  child.stdin.end();
  await Promise.all([new Response(child.stdout).text(), new Response(child.stderr).text()]);
  if (await child.exited !== 0) throw new Error("Named history checkout failed");
}
export async function stagePlannerHistory(root: string, inputs: PlanInputs, now: string) {
  const today = new Date(now);
  const nextDay = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate() + 1)).toISOString().slice(0, 10);
  const withBoundary = (days: string[]) => [...new Set([...days, nextDay])].sort();
  const plans = [
    { entry: inputs.registrations.discovered_articles,
      days: withBoundary(requiredUtcDays(now, inputs.harvest.config.discovered_articles.lookback_days)),
      authored: inputs.settings.inputs.discovered_days },
    { entry: inputs.registrations.published, days: withBoundary(requiredUtcDays(now, inputs.clock_config.collect.published_window_days)),
      authored: inputs.settings.inputs.published_days },
    { entry: inputs.registrations.item_health, days: withBoundary([now.slice(0, 10)]),
      authored: inputs.settings.inputs.settled_failure_days },
    { entry: inputs.registrations.selected_articles, days: withBoundary([now.slice(0, 10)]), authored: [] },
  ];
  const healthDays = withBoundary([...closedRequestDays(now, inputs.harvest.config.feedback.request_report_closed_days), now.slice(0, 10)]);
  const revision = await fixedHistoryRevision(root);
  const trees = new Map<string, Promise<string>>();
  const metadata = new Set<string>(["frontend/public/publication.json"]);
  for (const plan of plans) for (const day of createHistoryDayInputs(plan.entry.prefix, plan.days)) {
    for (const path of Object.values(day.indexes)) metadata.add(path);
    if (day.raw_index !== undefined) metadata.add(day.raw_index);
  }
  for (const day of [...inputs.settings.inputs.feed_health_days,
    ...createHistoryDayInputs(inputs.registrations.feed_health_state.prefix, healthDays),
    ...plans.flatMap(plan => plan.authored)]) {
    for (const path of Object.values(day.indexes ?? {})) if (path !== undefined) metadata.add(path);
    if (day.raw_index !== undefined) metadata.add(day.raw_index);
  }
  await stageNamedFiles(root, [...metadata]);
  const cache = new Map<string, Promise<unknown | undefined>>();
  function read(path: string) {
    let pending = cache.get(path);
    if (pending === undefined) {
      pending = (async () => {
        if (!metadata.has(path)) {
          await stageNamedFiles(root, [path]);
          metadata.add(path);
        }
        const content = await readNamedGitFile(root, path, revision);
        if (content === undefined) return undefined;
        try { return JSON.parse(content) as unknown; }
        catch (error) {
          if (error instanceof SyntaxError) throw new LedgerHistoryReadError("Native history JSON was refused", { cause: error });
          throw error;
        }
      })();
      cache.set(path, pending);
    }
    return pending;
  }
  const inventory = new Set<string>(inputs.settings.inputs.discovered_files);
  const compactCache = new Map<string, Promise<CompactIndex | undefined>>();
  function readCompact(path: string) {
    let pending = compactCache.get(path);
    if (pending === undefined) { pending = read(path).then(value => value === undefined ? undefined : CompactIndexSchema.parse(value)); compactCache.set(path, pending); }
    return pending;
  }
  for (const plan of plans) {
    const days = completeHistoryDayInputs(plan.entry.prefix, plan.days, plan.authored, plan.entry.name);
    await mapPool(days, inputs.harvest.config.harvest.concurrency, async day => {
      const indexes = resolveHistoryIndexes(plan.entry.prefix, day.indexes);
      const compact = (await Promise.all(Object.values(indexes).map(readCompact))).filter((value): value is CompactIndex => value !== undefined);
      const planner = PlannerLedgerNameSchema.safeParse(plan.entry.name).success;
      if (planner && day.raw_revision !== undefined && day.raw_revision !== revision) {
        throw new LedgerHistoryReadError("Authored raw history revision differs from the captured staging revision");
      }
      const listing = planner ? await listExactRawDayMembers(root, plan.entry, day.day, revision, trees) : undefined;
      const rawFiles = listing?.members.map(member => member.path) ?? day.raw_files ?? [];
      if (planner && day.raw_files !== undefined && [...day.raw_files].sort().join("\n") !== [...rawFiles].sort().join("\n")) {
        throw new LedgerHistoryReadError("Authored raw members omit or add files from the named Git day");
      }
      const raw = !planner && day.raw_index !== undefined ? await read(day.raw_index) : undefined;
      for (const path of resolveHistoryInventory({ ledger: LedgerNameSchema.parse(plan.entry.name),
        prefix: plan.entry.prefix, days: [day.day], compact, rawFiles, indexes,
        raw: raw === undefined ? [] : [RawDayIndexSchema.parse(raw)],
        ...(day.raw_index === undefined ? {} : { rawIndexes: { [day.day]: day.raw_index } }),
      })) inventory.add(path);
      for (const path of day.raw_files ?? []) inventory.add(path);
    });
  }
  if (inputs.settings.inputs.feed_health_days.some(day => day.raw_revision !== undefined && day.raw_revision !== revision)) {
    throw new LedgerHistoryReadError("Authored health revision differs from the captured staging revision");
  }
  const health = await stageFeedHistory({
    ledger: "feed-health-state", prefix: inputs.registrations.feed_health_state.prefix, now,
    health_window_days: Math.max(inputs.harvest.config.feedback.lifecycle_window_days, inputs.clock_config.collect.reliability_window_days),
    request_report_closed_days: inputs.harvest.config.feedback.request_report_closed_days,
    period_limit: inputs.settings.inputs.health_period_limit, authored: inputs.settings.inputs.feed_health_days, read,
    raw_files: async day => (await listExactRawDayMembers(root, inputs.registrations.feed_health_state, day, revision, trees))
      .members.map(member => member.path),
    read_period: async path => {
      await stageNamedFiles(root, [path]);
      await readNamedGitFile(root, path, revision);
      return (await readPlannerParquet(resolve(root, path), "feed-health-state", FeedHealthStateRowContract)).rows;
    },
  });
  for (const path of health.files) inventory.add(path);
  await stageNamedFiles(root, [...inventory]);
  for (const plan of plans.filter(plan => PlannerLedgerNameSchema.safeParse(plan.entry.name).success)) {
    for (const day of completeHistoryDayInputs(plan.entry.prefix, plan.days, plan.authored, plan.entry.name)) {
      for (const member of (await listExactRawDayMembers(root, plan.entry, day.day, revision, trees)).members) {
        await verifyRawDayMember(root, member);
      }
    }
  }
  return {
    feed_health_days: health.inputs.map(day => ({ ...day, raw_revision: revision })),
    feed_health_input_gap: health.notices.some(notice => notice.startsWith("health_")),
    notices: health.notices,
  };
}
