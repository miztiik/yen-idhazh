/** Which named UTC days support publication overlap and novelty readings? */
import { DateStampSchema, PositiveCountSchema } from "@idhazh/common-contracts";
import { UtcInstantSchema } from "../screen-article-candidates/seen-evidence";
import { uniquePublishedArticles } from "./fingerprint-dedup";
import type { PublishedArticle } from "./fingerprint-dedup";

// UTC calendar arithmetic uses milliseconds per day, not a local clock.
const UTC_DAY_MS = 86_400_000;
export type HistorySettings = Readonly<{ rolling_window_days: number; overlap_windows_days: readonly number[] }>;
export type PublicationDay = Readonly<{
  day: string; status: "rows" | "empty" | "missing" | "lost";
  articles: readonly PublishedArticle[];
}>;
export type HistoryWindow = Readonly<{
  as_of: string; start: string; end: string; days: readonly PublicationDay[];
  measured: readonly PublicationDay[]; required_days: number; coverage_days: number;
  availability: "available" | "unavailable";
}>;
export type HistoryReading = Readonly<{
  value: number | null; numerator: number | null; denominator: number | null;
  coverage_days: number; required_days: number;
  unavailable_reason: "incomplete_history" | "empty_denominator" | "missing_event_evidence" | null;
}>;

export function shiftUtcDay(day: string, offset: number): string {
  DateStampSchema.parse(day);
  if (!Number.isSafeInteger(offset)) throw new Error("UTC day offset must be an integer");
  const instant = Date.parse(`${day}T00:00:00Z`);
  if (!Number.isFinite(instant) || new Date(instant).toISOString().slice(0, 10) !== day) throw new Error("Invalid UTC calendar day");
  return new Date(instant + offset * UTC_DAY_MS).toISOString().slice(0, 10);
}
export function requiredHistoryDays(asOf: string, settings: HistorySettings, through?: string): string[] {
  const today = UtcInstantSchema.parse(asOf).slice(0, 10);
  const end = through ?? today;
  shiftUtcDay(end, 0);
  if (end > today) throw new Error("History cannot end after the UTC observation day");
  const rolling = PositiveCountSchema.parse(settings.rolling_window_days);
  if (settings.overlap_windows_days.length === 0) throw new Error("At least one overlap window is required");
  const overlaps = settings.overlap_windows_days.map(days => PositiveCountSchema.parse(days));
  const count = rolling + Math.max(rolling, ...overlaps);
  return Array.from({ length: count }, (_, index) => shiftUtcDay(end, index - count + 1));
}
export function buildHistoryWindow(asOf: string, settings: HistorySettings, input: readonly PublicationDay[], through?: string): HistoryWindow {
  const named = requiredHistoryDays(asOf, settings, through);
  const byDay = new Map<string, PublicationDay>();
  for (const day of input) {
    if (!named.includes(day.day)) throw new Error("History input is outside the configured named UTC days");
    if (byDay.has(day.day)) throw new Error("History input repeats a UTC day");
    if (!["rows", "empty", "missing", "lost"].includes(day.status)) throw new Error("Unknown history day status");
    if ((day.status === "rows") !== (day.articles.length > 0)) throw new Error("History status differs from article membership");
    if (day.articles.some(article => article.date !== day.day || article.run_id.slice(0, 10) !== day.day)) throw new Error("Historical article belongs to another UTC day");
    byDay.set(day.day, { ...day, articles: uniquePublishedArticles(day.articles) });
  }
  const days = named.map(day => byDay.get(day) ?? { day, status: "missing" as const, articles: [] });
  const measured = days.slice(-settings.rolling_window_days);
  const end = named[named.length - 1]!;
  const coverage = days.filter(day => available(day, asOf)).length;
  // Today's manifest is a partial observation until the next UTC midnight.
  return { as_of: asOf, start: measured[0]!.day, end, days, measured,
    required_days: days.length, coverage_days: coverage,
    availability: coverage === days.length ? "available" : "unavailable" };
}
function prior(window: HistoryWindow, day: string, count: number): readonly PublicationDay[] {
  PositiveCountSchema.parse(count);
  const from = shiftUtcDay(day, -count);
  const named = window.days.filter(held => held.day >= from && held.day < day);
  if (named.length !== count) throw new Error("Requested prior window exceeds the named history input");
  return named;
}
function available(day: PublicationDay, asOf: string): boolean {
  return (day.status === "rows" || day.status === "empty") && day.day < asOf.slice(0, 10);
}
function reading(numerator: number, denominator: number, days: readonly PublicationDay[], asOf: string): HistoryReading {
  const coverage = days.filter(day => available(day, asOf)).length;
  const reason = coverage !== days.length ? "incomplete_history" : denominator === 0 ? "empty_denominator" : null;
  return { value: reason === null ? numerator / denominator : null,
    numerator: reason === "incomplete_history" ? null : numerator,
    denominator: reason === "incomplete_history" ? null : denominator,
    coverage_days: coverage, required_days: days.length, unavailable_reason: reason };
}
function measuredDays(window: HistoryWindow, articles: readonly PublishedArticle[], named?: readonly string[]): readonly PublicationDay[] {
  const dates = named ?? window.measured.map(day => day.day);
  if (new Set(dates).size !== dates.length || dates.length === 0) throw new Error("Measurement must name distinct UTC days");
  if (articles.some(article => !dates.includes(article.date))) throw new Error("Article is outside the named measurement days");
  return dates.map(date => {
    const day = window.days.find(day => day.day === date);
    if (day === undefined || date < window.start || date > window.end) throw new Error("Measurement day is outside the rolling window");
    return day;
  });
}
export function sourceOverlap(window: HistoryWindow, current: readonly PublishedArticle[], count: number, dates?: readonly string[]): HistoryReading {
  const articles = uniquePublishedArticles(current);
  const left = new Set<string>();
  const right = new Set<string>();
  const required = new Map<string, PublicationDay>();
  const measured = measuredDays(window, articles, dates);
  for (const day of measured) {
    required.set(day.day, day);
    for (const held of prior(window, day.day, count)) {
      required.set(held.day, held);
      for (const article of held.articles) right.add(article.source_id);
    }
  }
  for (const article of articles) left.add(article.source_id);
  const union = new Set([...left, ...right]);
  const intersection = [...left].filter(source => right.has(source)).length;
  return reading(intersection, union.size, [...required.values()], window.as_of);
}
export function novelSourceContribution(window: HistoryWindow, current: readonly PublishedArticle[], count: number, dates?: readonly string[]): HistoryReading {
  const articles = uniquePublishedArticles(current);
  const required = new Map<string, PublicationDay>();
  for (const day of measuredDays(window, articles, dates)) {
    required.set(day.day, day);
    for (const held of prior(window, day.day, count)) required.set(held.day, held);
  }
  let novel = 0;
  for (const article of articles) {
    const history = prior(window, article.date, count);
    for (const day of history) required.set(day.day, day);
    if (!history.some(day => day.articles.some(held => held.source_id === article.source_id))) novel++;
  }
  return reading(novel, articles.length, [...required.values()], window.as_of);
}
export function unavailableEvents(days: readonly PublicationDay[], asOf: string): HistoryReading {
  const coverage = days.filter(day => available(day, asOf)).length;
  return { value: null, numerator: null, denominator: null, coverage_days: coverage, required_days: days.length,
    unavailable_reason: coverage === days.length ? "missing_event_evidence" : "incomplete_history" };
}
