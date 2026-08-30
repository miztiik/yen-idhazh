import { chartConfig, consoleConfig, uiConfig } from '$lib/server/config';
import { modelByDate, modelWork } from '$lib/server/model-work';
import type { RateSpread, ThroughputDay } from '$lib/charts/series';
import { evalRows, itemHealthRows } from '$lib/server/payload';

export const prerender = true;

export type { CapPoint, ModelDay, ModelRow } from '$lib/server/model-work';

function measured(row: Record<string, string>, name: string): number | null {
	const raw = row[name];
	if (raw === undefined || raw === '') return null;
	const value = Number(raw);
	return Number.isFinite(value) ? value : null;
}

function byDate(rows: Record<string, string>[]): Map<string, Record<string, string>[]> {
	const grouped = new Map<string, Record<string, string>[]>();
	for (const row of rows) {
		const date = row.date ?? '';
		if (!date) continue;
		grouped.set(date, [...(grouped.get(date) ?? []), row]);
	}
	return grouped;
}

function quantile(sorted: number[], fraction: number): number {
	if (sorted.length === 1) return sorted[0];
	const position = (sorted.length - 1) * fraction;
	const low = Math.floor(position);
	const high = Math.ceil(position);
	return sorted[low] + (sorted[high] - sorted[low]) * (position - low);
}

function spread(values: number[]): RateSpread | null {
	if (values.length === 0) return null;
	const sorted = [...values].sort((a, b) => a - b);
	return {
		min: sorted[0],
		p25: quantile(sorted, 0.25),
		median: quantile(sorted, 0.5),
		p75: quantile(sorted, 0.75),
		max: sorted[sorted.length - 1]
	};
}

/** One item's two rates, or null where the runtime reported no timing.
 *
 * Cached prompt tokens are taken out of the read count. Leaving them in reports
 * a rate the machine never ran at: it did not read them.
 */
function itemRates(row: Record<string, string>): { read: number | null; write: number | null } {
	const prefillMs = measured(row, 'prefill_ms');
	const decodeMs = measured(row, 'decode_ms');
	const prompt = measured(row, 'input_tokens');
	const written = measured(row, 'output_tokens');
	const evaluated = prompt === null ? null : prompt - (measured(row, 'cached_tokens') ?? 0);
	return {
		read:
			prefillMs !== null && prefillMs > 0 && evaluated !== null && evaluated > 0
				? evaluated / (prefillMs / 1000)
				: null,
		write:
			decodeMs !== null && decodeMs > 0 && written !== null && written > 0
				? written / (decodeMs / 1000)
				: null
	};
}

/** What the model did to the day's own articles.
 *
 * The same two ledgers the Pipelines route reads, asked a different question.
 * Nothing here is a rate the pipeline stored: every ratio is one committed
 * count over another, computed at read time, so a ratio can never disagree with
 * the counts printed beside it.
 */
export async function load() {
	const { rows } = evalRows();
	const itemRows = itemHealthRows().rows;
	const modelOnDate = modelByDate(rows);
	const itemHealthByDate = byDate(itemRows);

	// Two different statistics, both kept on purpose. The candle is the spread of
	// per-item rates, because the worker sorts short articles first and the two
	// ends of a day drift apart. The day figure is the sum of the parts, because
	// a rate is a ratio and averaging per-item rates weighs a release note like a
	// feature. Oldest first: the chart reads left to right.
	const throughputDays: ThroughputDay[] = [...itemHealthByDate.entries()]
		.map(([date, group]) => {
			const reads: number[] = [];
			const writes: number[] = [];
			const perRun = new Map<string, { read: number[]; write: number[] }>();
			let prefillMs = 0;
			let decodeMs = 0;
			let cached = 0;
			let prompt = 0;
			let written = 0;
			for (const row of group) {
				const rate = itemRates(row);
				if (rate.read === null && rate.write === null) continue;
				const bucket = perRun.get(row.run_id ?? '') ?? { read: [], write: [] };
				if (rate.read !== null) {
					reads.push(rate.read);
					bucket.read.push(rate.read);
				}
				if (rate.write !== null) {
					writes.push(rate.write);
					bucket.write.push(rate.write);
				}
				perRun.set(row.run_id ?? '', bucket);
				prefillMs += measured(row, 'prefill_ms') ?? 0;
				decodeMs += measured(row, 'decode_ms') ?? 0;
				cached += measured(row, 'cached_tokens') ?? 0;
				prompt += measured(row, 'input_tokens') ?? 0;
				written += measured(row, 'output_tokens') ?? 0;
			}
			const read = spread(reads);
			const write = spread(writes);
			if (read === null || write === null) return null;
			const evaluated = Math.max(prompt - cached, 0);
			return {
				date,
				items: Math.max(reads.length, writes.length),
				read,
				write,
				readTps: prefillMs > 0 ? evaluated / (prefillMs / 1000) : 0,
				writeTps: decodeMs > 0 ? written / (decodeMs / 1000) : 0,
				cacheHitPct: prompt > 0 ? (cached / prompt) * 100 : 0,
				model: modelOnDate.get(date) ?? null,
				runs: [...perRun.entries()]
					.map(([runId, bucket]) => ({
						runId,
						items: Math.max(bucket.read.length, bucket.write.length),
						read: spread(bucket.read)?.median ?? 0,
						write: spread(bucket.write)?.median ?? 0
					}))
					.sort((a, b) => a.runId.localeCompare(b.runId))
			};
		})
		.filter((day): day is ThroughputDay => day !== null)
		.sort((a, b) => a.date.localeCompare(b.date));

	return {
		modelWork: modelWork(rows, itemRows),
		throughputDays,
		// The explanation lives in docs/, which the site does not publish, so the
		// chart points at the repository rather than restating it in a caption.
		throughputReference: `${uiConfig().repo_url.replace(/\/+$/, '')}/blob/main/docs/architecture/summarize/throughput.md`,
		// Every fixed benchmark figure lives in the write-up and none of them is
		// copied onto this page: two machines and two workloads, so a gap between a
		// bench number and a run reads as a regression nobody measured.
		measurementsReference: `${uiConfig().repo_url.replace(/\/+$/, '')}/blob/main/docs/reference/measurements.md`,
		console: consoleConfig(),
		chart: chartConfig(),
		today: new Date().toISOString().slice(0, 10)
	};
}
