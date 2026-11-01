/** How are current and historical requests shown once with category-specific coverage? */
import type { FeedHealthStateRow, PlannerRequestReport } from "@idhazh/common-contracts";
import { escapeMarkdown } from "./markdown-format";
import { aggregateFeedResults, compareKnownDescending } from "./aggregate-feed-results";

const fields = ["article_requests", "feed_requests", "robots_requests"] as const;
const labels = { article_requests: "Article", feed_requests: "Feed", robots_requests: "Robots" };
type CoverageRow = { applies: string[]; recorded: number; complete: number; missing: number; window: string; expected: number };

export function renderRequestReport(requests: PlannerRequestReport | undefined, health?: readonly FeedHealthStateRow[]) {
  const countRows: string[][] = [];
  const coverageGroups = new Map<string, CoverageRow>();
  const addCoverage = (applies: string, window: string, expected: number, recorded: number, complete: number, missing: number) => {
    const key = JSON.stringify([window, expected, recorded, complete, missing]);
    const group = coverageGroups.get(key) ?? { applies: [], window, expected, recorded, complete, missing };
    group.applies.push(applies);
    coverageGroups.set(key, group);
  };
  const sorted = <T extends { feed_id: string; article_requests: number | null; feed_requests: number | null }>(rows: T[]) =>
    rows.sort((a, b) => compareKnownDescending(a.article_requests, b.article_requests)
      || compareKnownDescending(a.feed_requests, b.feed_requests) || a.feed_id.localeCompare(b.feed_id));
  const currentDays = [...new Set(health?.map(row => row.date))].sort();
  const currentWindow = currentDays.length ? `${currentDays[0]} through ${currentDays.at(-1)}` : "Not recorded";
  for (const feed of sorted(aggregateFeedResults(health ?? []))) {
    const rows = health!.filter(row => row.feed_id === feed.feed_id);
    const coverage = fields.map(field => {
      const known = rows.filter(row => row[field] !== null);
      const missing = rows.length - known.length;
      addCoverage(`This run: ${feed.feed_id}, ${labels[field].toLowerCase()} requests`, currentWindow,
        currentDays.length, new Set(known.map(row => row.date)).size,
        currentDays.filter(day => !rows.some(row => row.date === day && row[field] === null)).length, missing);
      return `${labels[field]}: ${missing === 0 ? "complete" : known.length ? "partial" : "not recorded"}`;
    });
    // Partial request subtotals differ from exact per-feed article totals.
    const counters = fields.map(field => {
      const known = rows.flatMap(row => row[field] === null ? [] : [row[field]]);
      return known.length ? String(known.reduce((sum, value) => sum + value, 0)) : "Not recorded";
    });
    countRows.push(["This run", feed.feed_id, ...counters, coverage.join("; ")]);
  }
  if (requests !== undefined) {
    const expected = (Date.parse(requests.through_day) - Date.parse(requests.from_day)) / 86_400_000 + 1;
    const window = `${requests.from_day} through ${requests.through_day}`;
    for (const feed of sorted([...requests.feeds])) {
      const coverage = fields.map(field => {
        const value = feed.coverage[field];
        addCoverage(`Historical window: ${feed.feed_id}, ${labels[field].toLowerCase()} requests`, window,
          expected, value.recorded_days.length, value.complete_days.length, value.unknown_records);
        return `${labels[field]}: ${value.status === "none" ? "not recorded" : value.status}`;
      });
      countRows.push(["Historical window", feed.feed_id, ...fields.map(field => String(feed[field] ?? "Not recorded")), coverage.join("; ")]);
    }
  }
  const coverageRows = [...coverageGroups.values()];
  const describeApplies = (applies: string[]) => {
    const descriptions: string[] = [];
    for (const [period, feedIds] of [
      ["This run", aggregateFeedResults(health ?? []).map(feed => feed.feed_id)],
      ["Historical window", requests?.feeds.map(feed => feed.feed_id) ?? []],
    ] as const) {
      const categories = new Map<string, string[]>();
      for (const field of fields) {
        const matching = feedIds.filter(id => applies.includes(`${period}: ${id}, ${labels[field].toLowerCase()} requests`));
        if (matching.length === 0) continue;
        const excluded = feedIds.filter(id => !matching.includes(id));
        const scope = excluded.length === 0 ? `all ${feedIds.length} ${feedIds.length === 1 ? "feed" : "feeds"}`
          : excluded.length < matching.length ? `all feeds except ${excluded.join(", ")}` : matching.join(", ");
        const held = categories.get(scope) ?? [];
        held.push(labels[field].toLowerCase());
        categories.set(scope, held);
      }
      for (const [scope, categoriesForScope] of categories) {
        descriptions.push(`${period}: ${scope}; ${categoriesForScope.join(", ")} requests`);
      }
    }
    return descriptions.join("; ");
  };
  return {
    markdown: [
      "<details>", "<summary>Request counts and coverage</summary>", "",
      "Partial totals contain recorded requests only. Missing counts are not estimates. Zero is known zero.",
      "", "## Table D - Request counts by feed", "",
      "| Id | Period | Feed | Article requests | Feed requests | Robots requests | Coverage |",
      "| --- | --- | --- | --- | --- | --- | --- |",
      ...countRows.map((cells, index) => `| D${index + 1} | ${cells.map(escapeMarkdown).join(" | ")} |`),
      ...(health === undefined ? ["", "This run's request counts were not recorded."] : []),
      ...(requests === undefined ? ["", "Request history was not recorded."] : []),
      "", "## Table E - Request coverage", "",
      "| Id | Applies to | Window (UTC dates) | Recorded days / expected | Complete days / expected | Records with missing counts |",
      "| --- | --- | --- | --- | --- | --- |",
      ...coverageRows.map((row, index) => `| E${index + 1} | ${escapeMarkdown(describeApplies(row.applies))} | ${row.window} | ${row.recorded} / ${row.expected} | ${row.complete} / ${row.expected} | ${row.missing} |`),
      "", "Complete known-empty days need not contain observed records. Missing files do not establish how many records are missing.",
      "Shared coverage rows apply to each named feed and request category, not a sum across them.",
      ...(requests === undefined ? [] : [
        `Missing or incomplete day files: ${requests.missing_days.join(", ") || "none"}.`,
        `Days with records that cannot be attributed: ${requests.unattributed_days.join(", ") || "none"}.`,
        `Staged history inputs: ${requests.input_complete ? "complete" : "incomplete; missing records may affect any day"}.`,
      ]),
      "", "</details>",
    ].join("\n"),
    notice: requests === undefined ? "Request history was not recorded."
      : `Historical requests: ${requests.complete ? "complete" : "partial"} coverage.`,
  };
}
