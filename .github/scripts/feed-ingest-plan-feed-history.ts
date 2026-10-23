/** Which existing native inventory and explicit day inputs supply feed-health history? */
import { CompactIndexSchema, RawDayIndexSchema } from "../../packages/common-contracts/src/index";
import type { CompactIndex } from "../../packages/common-contracts/src/index";
import { SeenDayInputSchema } from "../../services/feed-ingest-plan/src/config/service-settings";
import type { SeenDayInput } from "../../services/feed-ingest-plan/src/config/service-settings";
import { resolveHealthInventory } from "../../services/feed-ingest-plan/src/read-ledger-history/read-health-inventory";
import { createSeenDayInputs, resolveHistoryInventory } from "./feed-ingest-plan-outputs";

export async function stageFeedHistory(input: {
  ledger: "feed-health"; prefix: readonly string[];
  now: string; health_window_days: number; authored: readonly SeenDayInput[];
  read: (path: string) => Promise<unknown | undefined>;
}) {
  const defaults = createSeenDayInputs(input.prefix, [input.now.slice(0, 10)])[0]!;
  const compact: Partial<Record<CompactIndex["period"], CompactIndex>> = {};
  for (const period of ["yearly", "monthly", "daily"] as const) {
    const value = await input.read(defaults.indexes[period]);
    if (value !== undefined) compact[period] = CompactIndexSchema.parse(value);
  }
  const native = resolveHealthInventory({
    ledger: input.ledger, prefix: input.prefix,
    inventory: await input.read("frontend/public/publication.json"),
    compact, health_window_days: input.health_window_days,
  });
  const authored = input.authored.map(day => SeenDayInputSchema.parse(day));
  if (authored.some((day, index) => day.day > input.now.slice(0, 10)
    || (index > 0 && day.day <= authored[index - 1]!.day))) {
    throw new Error("Feed history authored inputs must be distinct ascending days no later than the run");
  }
  const inputs = new Map(native.inputs.map(day => [day.day, day]));
  const files = new Set(native.files);
  const notices = [...native.notices];
  // A single named current-day index supplements inventory; it never becomes a directory census.
  const supplemental: SeenDayInput[] = authored.some(day => day.day === defaults.day) ? authored : [...authored, defaults];
  for (const named of supplemental) {
    if (named.indexes !== undefined && Object.entries(named.indexes).some(([period, path]) =>
      path !== defaults.indexes[period as keyof typeof defaults.indexes])) {
      throw new Error("Feed history requires the registered native compact index paths");
    }
    const covered = Object.values(compact).some(index => index.entries.some(entry =>
      named.day === entry.covers || named.day.startsWith(`${entry.covers}-`)));
    if (covered) continue;
    const value = named.raw_index === undefined ? undefined : await input.read(named.raw_index);
    const raw = value === undefined ? [] : [RawDayIndexSchema.parse(value)];
    for (const path of resolveHistoryInventory({
      ledger: input.ledger, prefix: input.prefix, days: [named.day],
      compact: Object.values(compact), raw,
      ...(named.raw_index === undefined ? {} : { rawIndexes: { [named.day]: named.raw_index } }),
    })) files.add(path);
    if ((named.raw_files?.length ?? 0) === 0 && !raw.some(index => index.files.length > 0)) {
      if (!inputs.has(named.day)) notices.push(`feed-inventory:supplement-unavailable:${input.ledger}:${named.day}`);
      continue;
    }
    const previous = inputs.get(named.day);
    const rawFiles = named.raw_files === undefined ? undefined
      : [...new Set([...(previous?.raw_files ?? []), ...named.raw_files])].sort();
    inputs.set(named.day, SeenDayInputSchema.parse({
      ...named, indexes: defaults.indexes, ...(rawFiles === undefined ? {} : { raw_files: rawFiles }),
    }));
    for (const path of rawFiles ?? []) files.add(path);
  }
  const selected = [...inputs.values()].sort((a, b) => a.day.localeCompare(b.day)).slice(-input.health_window_days);
  if (selected.some(day => day.day > input.now.slice(0, 10))) throw new Error("Feed history inventory exceeds the captured UTC day");
  return {
    inputs: selected, files: [...files].sort(),
    represented_days: selected.map(day => day.day), inventory_complete: false as const, notices,
  };
}
