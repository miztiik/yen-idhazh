/** Which existing native files serve the feed-history days Python would select? */
import {
  COMPACT_INDEX_VERSION, CompactIndexSchema, DateStampSchema, FileIdNameSchema,
  NativeRelativePathSchema, PublicationInventoryInputSchema, PublicationReceiptInputSchema,
  WriterIdentitySchema,
} from "@idhazh/common-contracts";
import type { CompactIndex, WriterIdentity } from "@idhazh/common-contracts";
import type { SeenDayInput } from "../config/service-settings";

type FeedLedger = "feed-health" | "feed-retirements";
type Period = CompactIndex["period"];
export type FeedReceiptWrite = Readonly<{
  path: string; sha256: string; day: string; identity: WriterIdentity;
}>;
export type FeedInventory = Readonly<{
  inputs: SeenDayInput[];
  files: string[];
  receipt_writes: FeedReceiptWrite[];
  inventory_complete: false;
  notices: string[];
}>;
export type FeedInventoryInput = Readonly<{
  ledger: FeedLedger;
  prefix: readonly string[];
  inventory: unknown;
  compact: Readonly<Partial<Record<Period, unknown>>>;
  health_window_days: number;
  receipts?: readonly Readonly<{ value: unknown; identity: WriterIdentity }>[];
}>;
const periods = ["yearly", "monthly", "daily"] as const;

function calendarDays(covers: string): string[] {
  if (covers.length === 10) {
    const day = DateStampSchema.parse(covers);
    if (new Date(`${day}T00:00:00Z`).toISOString().slice(0, 10) !== day) {
      throw new Error("feed inventory: invalid UTC calendar day");
    }
    return [day];
  }
  const first = covers.length === 4 ? `${covers}-01-01` : `${covers}-01`;
  const clock = new Date(`${first}T00:00:00Z`);
  if (!Number.isFinite(clock.valueOf()) || !clock.toISOString().startsWith(first)) {
    throw new Error("feed inventory: invalid UTC calendar period");
  }
  const days: string[] = [];
  while (clock.toISOString().startsWith(`${covers}-`)) {
    days.push(clock.toISOString().slice(0, 10));
    clock.setUTCDate(clock.getUTCDate() + 1);
  }
  return days;
}
function rawDay(path: string, root: string): string | undefined {
  if (!path.startsWith(`${root}/`)) return undefined;
  const parts = path.slice(root.length + 1).split("/");
  if (parts.length !== 4 || !FileIdNameSchema.safeParse(parts[3]).success) {
    throw new Error("feed inventory: native raw entry must name one UTC day's UUID file");
  }
  const day = parts.slice(0, 3).join("-");
  calendarDays(day);
  if (!path.endsWith(".parquet")) throw new Error("feed inventory: native JSON rows require a JSON reader");
  return day;
}
function sameWriter(left: WriterIdentity, right: WriterIdentity): boolean {
  return (Object.keys(WriterIdentitySchema.shape) as (keyof WriterIdentity)[])
    .every(key => left[key] === right[key]);
}
function compactPath(root: string, period: Period, covers: string): string {
  return `${root}/${period}/${period === "yearly" ? `${covers}/${covers}` : covers.replaceAll("-", "/")}.parquet`;
}

export function resolveFeedInventory(input: FeedInventoryInput): FeedInventory {
  if (!Number.isSafeInteger(input.health_window_days) || input.health_window_days < 1) {
    throw new Error("feed inventory: health_window_days must be a positive recorded-day count");
  }
  if (input.prefix.length === 0 || input.prefix.some(part => !/^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/.test(part))) {
    throw new Error("feed inventory: prefix must be a registered native ledger prefix");
  }
  const prefix = input.prefix.join("/");
  const rawRoot = `state/raw/${prefix}`;
  const compactRoot = `state/compact/${prefix}`;
  const indexes = Object.fromEntries(periods.map(period => [period, `${compactRoot}/index/${period}.json`]));
  const compact = new Map<Period, CompactIndex>();
  const notices: string[] = [];
  for (const period of periods) {
    const value = input.compact[period];
    if (value === undefined) {
      notices.push(`feed-inventory:index-missing:${input.ledger}:${period}`);
      continue;
    }
    const index = CompactIndexSchema.parse(value);
    if (index.version > COMPACT_INDEX_VERSION || index.ledger !== input.ledger || index.period !== period) {
      throw new Error("feed inventory: compact index version, ledger or period differs from its named input");
    }
    compact.set(period, index);
    if (index.expired_through !== null) {
      notices.push(`feed-inventory:expired-through:${input.ledger}:${index.expired_through}`);
    }
  }
  const raw = new Map<string, Set<string>>();
  const addRaw = (path: string) => {
    NativeRelativePathSchema.parse(path);
    const day = rawDay(path, rawRoot);
    if (day === undefined) return;
    let held = raw.get(day);
    if (held === undefined) raw.set(day, held = new Set());
    held.add(path);
  };
  if (input.inventory === undefined) {
    notices.push(`feed-inventory:publication-inventory-missing:${input.ledger}`);
  } else {
    const inventory = PublicationInventoryInputSchema.parse(input.inventory);
    for (const entry of inventory.entries) {
      if (entry.root === "state") addRaw(`state/${entry.path}`);
    }
  }
  const receiptWrites = new Map<string, FeedReceiptWrite>();
  for (const supplied of input.receipts ?? []) {
    const receipt = PublicationReceiptInputSchema.parse(supplied.value);
    const expected = WriterIdentitySchema.parse(supplied.identity);
    if (!sameWriter(receipt.identity, expected)) throw new Error("feed inventory: receipt belongs to another invocation");
    for (const [path, sha256] of Object.entries(receipt.writes)) {
      const day = rawDay(path, rawRoot);
      if (day === undefined) continue;
      const previous = receiptWrites.get(path);
      if (previous !== undefined && previous.sha256 !== sha256) {
        throw new Error("feed inventory: conflicting exact receipts name the same native file");
      }
      receiptWrites.set(path, { path, sha256, day, identity: receipt.identity });
      addRaw(path);
    }
  }
  const matchPeriod = (day: string) => periods.flatMap(period => {
    const covers = period === "yearly" ? day.slice(0, 4) : period === "monthly" ? day.slice(0, 7) : day;
    const entry = compact.get(period)?.entries.find(entry => entry.covers === covers);
    return entry === undefined ? [] : [{ period, entry }];
  })[0];
  const days = new Set<string>();
  for (const index of compact.values()) {
    for (const entry of index.entries) {
      // Python held_days includes every calendar day of a nonempty packed period.
      if (input.ledger === "feed-retirements" || entry.rows > 0) {
        for (const day of calendarDays(entry.covers)) days.add(day);
      }
    }
  }
  const receiptDays = new Set([...receiptWrites.values()].map(write => write.day));
  for (const day of raw.keys()) {
    if (matchPeriod(day) === undefined || receiptDays.has(day)) days.add(day);
    else if (!days.has(day)) {
      notices.push(`feed-inventory:covered-raw-day-unconfirmed:${input.ledger}:${day}`);
    }
  }
  const heldDays = [...days].sort();
  const selected = input.ledger === "feed-health"
    ? heldDays.slice(-input.health_window_days) : heldDays;
  const files = new Set(Object.values(indexes));
  const inputs: SeenDayInput[] = [];
  for (const day of selected) {
    const match = matchPeriod(day);
    if (match !== undefined) {
      if (match.entry.state === "packed") files.add(compactPath(compactRoot, match.period, match.entry.covers));
      inputs.push({ day, indexes });
    } else {
      const rawFiles = [...(raw.get(day) ?? [])].sort();
      for (const path of rawFiles) files.add(path);
      // An inventory entry proves a named file, not that it lists every writer of its day.
      inputs.push({ day, indexes, raw_files: rawFiles });
    }
  }
  notices.push(`feed-inventory:raw-census-unproven:${input.ledger}`);
  return {
    inputs, files: [...files].sort(), receipt_writes: [...receiptWrites.values()],
    inventory_complete: false, notices,
  };
}
