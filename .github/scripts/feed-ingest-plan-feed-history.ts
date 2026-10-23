/** Which named native files supply health and permanent retirement observations to the isolated run? */
import { COMPACT_INDEX_VERSION, CompactIndexSchema, DateStampSchema, RawDayIndexSchema } from "../../packages/common-contracts/src/index";
import type { CompactIndex } from "../../packages/common-contracts/src/index";
import { SeenDayInputSchema } from "../../services/feed-ingest-plan/src/config/service-settings";
import type { SeenDayInput } from "../../services/feed-ingest-plan/src/config/service-settings";
import { createSeenDayInputs, resolveHistoryInventory } from "./feed-ingest-plan-outputs";
import { requiredSeenDays } from "../../services/feed-ingest-plan/src/read-ledger-history/read-seen-evidence";

function compactDays(index: CompactIndex): string[] {
  return index.entries.flatMap(entry => {
    const first = `${entry.covers}${index.period === "yearly" ? "-01-01" : index.period === "monthly" ? "-01" : ""}`;
    const start = new Date(`${first}T00:00:00Z`);
    const end = new Date(start);
    if (index.period === "yearly") end.setUTCFullYear(end.getUTCFullYear() + 1);
    else if (index.period === "monthly") end.setUTCMonth(end.getUTCMonth() + 1);
    else end.setUTCDate(end.getUTCDate() + 1);
    const days: string[] = [];
    for (let instant = start.getTime(); instant < end.getTime(); instant += 86_400_000) {
      days.push(new Date(instant).toISOString().slice(0, 10));
    }
    return days;
  });
}

export async function stageFeedHistory(input: {
  ledger: "feed-health" | "feed-retirements"; prefix: readonly string[];
  now: string; raw_discovery_days: number; authored: readonly SeenDayInput[];
  read: (path: string) => Promise<unknown | undefined>;
  listRawDay: (directory: string) => Promise<readonly string[] | undefined>;
}) {
  const defaults = createSeenDayInputs(input.prefix, [input.now.slice(0, 10)])[0]!;
  const compact: CompactIndex[] = [];
  for (const [period, path] of Object.entries(defaults.indexes)) {
    const value = await input.read(path);
    if (value === undefined) continue;
    const index = CompactIndexSchema.parse(value);
    if (index.period !== period || index.ledger !== input.ledger || index.version > COMPACT_INDEX_VERSION) {
      throw new Error("Feed history compact index differs from its named ledger, period or supported version");
    }
    compact.push(index);
  }
  const authored = input.authored.map(day => SeenDayInputSchema.parse(day));
  if (authored.some((day, index) => day.day > input.now.slice(0, 10)
    || (index > 0 && day.day <= authored[index - 1]!.day))) {
    throw new Error("Feed history authored inputs must be distinct ascending days no later than the run");
  }
  const days = [...new Set([
    ...compact.flatMap(compactDays).filter(day => day <= input.now.slice(0, 10)),
    ...requiredSeenDays(input.now, input.raw_discovery_days), ...authored.map(day => day.day),
  ])].sort();
  const inventory = new Set<string>();
  const inputs: SeenDayInput[] = [];
  for (const day of days) {
    DateStampSchema.parse(day);
    const named: SeenDayInput = authored.find(input => input.day === day) ?? createSeenDayInputs(input.prefix, [day])[0]!;
    const rawPath = named.raw_index;
    const rawValue = rawPath === undefined ? undefined : await input.read(rawPath);
    const raw = rawValue === undefined ? [] : [RawDayIndexSchema.parse(rawValue)];
    const indexed = compact.some(index => index.entries.some(entry =>
      day === entry.covers || day.startsWith(`${entry.covers}-`)));
    let rawFiles: readonly string[] | undefined = named.raw_files;
    // Only a named UTC day is listed. A missing raw directory is not invented as an empty ledger day.
    if (rawFiles === undefined && raw.length === 0 && !indexed) {
      rawFiles = await input.listRawDay(`state/raw/${input.prefix.join("/")}/${day.replaceAll("-", "/")}`);
    }
    const resolved = rawFiles === undefined ? named : {
      day, indexes: named.indexes, raw_files: [...rawFiles],
    };
    inputs.push(SeenDayInputSchema.parse(resolved));
    for (const path of resolveHistoryInventory({
      ledger: input.ledger, prefix: input.prefix, days: [day], compact, raw,
      ...(named.indexes === undefined ? {} : { indexes: Object.fromEntries(Object.entries(named.indexes)
        .filter((entry): entry is [string, string] => entry[1] !== undefined)) }),
      ...(rawPath === undefined ? {} : { rawIndexes: { [day]: rawPath } }),
    })) inventory.add(path);
    for (const path of rawFiles ?? []) inventory.add(path);
    if (named.indexes !== undefined && Object.entries(named.indexes).some(([period, path]) =>
      path !== defaults.indexes[period as keyof typeof defaults.indexes])) {
      throw new Error("Feed history discovery requires the registered native compact index paths");
    }
  }
  return { inputs, files: [...inventory], inventory_complete: false as const };
}
