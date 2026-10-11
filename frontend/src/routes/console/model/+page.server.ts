import { chartConfig, consoleConfig, evaluationConfig, observabilityConfig, summarizeConfig, uiConfig } from '$lib/server/config';
import { evalDays, type DayScoredCounts } from '$lib/console/eval-instruments';
import { reasonDays } from '$lib/console/doubt-reasons';
import { modelWork, workDates } from '$lib/server/model-work';
import { evalRows, itemHealthRows } from '$lib/server/ledger-rows';
import { dayMetrics, loadDay, publishedDates } from '$lib/server/payload';
import { windowDay } from '$lib/server/window-day';
import { windowOfDays } from '$lib/charts/viewport';

export const prerender = true;
export type { CapPoint, DayWindow, Distribution, ModelDay, ModelRow, ModelSwap, RunLength, ScoreCost, SourceDoubt, SourceDoubts, SwapMeasure, WriteBin, WriteTimes } from '$lib/server/model-work';
export type { ReasonDay } from '$lib/console/doubt-reasons';
export type { EvalDay } from '$lib/console/eval-instruments';

/** Only the approved cards, daily disclosure and item decisions cross this boundary. */
export async function load() {
	const shared = consoleConfig();
	const widest = Math.max(...shared.window_presets);
	const day = windowDay();
	const span = windowOfDays(day, widest, shared.today_anchor);
	const [scores, health] = await Promise.all([evalRows(span), itemHealthRows(span)]);
	const metrics = dayMetrics(workDates(scores.rows, health.rows));
	const counts = new Map<string, DayScoredCounts>([...metrics].map(([date, record]) => [
		date, { scored: record.summariesScored, determinismViolations: record.determinismViolations, extractionSuspect: record.extractionSuspect }
	]));
	const days = modelWork(scores.rows, health.rows, counts).flatMap((row) => {
		if (row.kind !== 'day') return [];
		const settled = counts.get(row.day.date);
		return [{ ...row.day, models: [], summaries: settled?.scored ?? null,
			determinismViolations: settled?.determinismViolations ?? null }];
	});
	const instruments = evalDays(scores.rows, counts).map((value) => ({
		date: value.date,
		recorded: {
			self_repetition: value.recorded.self_repetition ?? null,
			coherence: value.recorded.coherence ?? null,
			semantic_coverage: value.date < '2026-09-24' ? null : value.recorded.semantic_coverage ?? null
		}
	}));
	const reasons = reasonDays(publishedDates(undefined, widest).flatMap((date) => {
		const payload = loadDay(date);
		return payload === null ? [] : [{ date, items: payload.items.map((item) => ({
			band: item.band, reason: item.band_reason
		})) }];
	}));
	const evaluation = evaluationConfig();
	const repo = uiConfig().repo_url.replace(/\/+$/, '');
	const recording = observabilityConfig();
	return {
		cardDays: days, instruments, reasons, windowDay: day, chart: chartConfig(),
		summarizeBands: summarizeConfig().bands,
		matchThresholds: { high: Math.round(evaluation.band_high_min * 100), low: Math.round(evaluation.band_medium_min * 100) },
		recording: { evaluationEnabled: recording.evaluation_enabled, sampleRate: recording.sample_rate },
		buildRecord: { scores: scores.read, article: health.read },
		throughputReference: `${repo}/blob/main/docs/architecture/summarize/throughput.md`,
		faithfulnessReference: `${repo}/blob/main/docs/architecture/publishing/autotune-summary-quality.md`
	};
}
