import { chartConfig, consoleConfig, evaluationConfig, observabilityConfig, summarizeConfig, uiConfig } from '$lib/server/config';
import { evalDays, type DayScoredCounts } from '$lib/console/eval-instruments';
import { reasonDays } from '$lib/console/doubt-reasons';
import { modelWork, workDates } from '$lib/server/model-work';
import { evalRows, itemHealthRows } from '$lib/server/ledger-rows';
import { dayMetrics, loadDay, publishedDates } from '$lib/server/payload';
import { windowDay } from '$lib/server/window-day';
import { windowOfDays } from '$lib/charts/viewport';
import { measurementOff, recordingNotes, recordNotesByWindow } from '$lib/console/recording';

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
	const windows = shared.window_presets.map((days) => ({ days, ...windowOfDays(day, days, shared.today_anchor) }));
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
	const published = publishedDates(undefined, widest);
	const decisions = published.flatMap((date) => {
		const payload = loadDay(date);
		return payload === null ? [] : [{ date, items: payload.items.map((item) => ({
			band: item.band, reason: item.band_reason
		})) }];
	});
	const reasons = published.length === 0 || decisions.length !== published.length ? null : reasonDays(decisions);
	const evaluation = evaluationConfig();
	const repo = uiConfig().repo_url.replace(/\/+$/, '');
	const recording = observabilityConfig();
	const scoredDays = [...new Set(scores.rows.map((row) => row.date).filter(Boolean))];
	const answeredDays = [...new Set(health.rows.map((row) => row.date).filter(Boolean))];
	const timedDays = [...new Set(health.rows.filter((row) => Number(row.summarize_ms) > 0).map((row) => row.date))];
	const notes = Object.fromEntries(windows.map((open) => [String(open.days), recordingNotes({
		enabled: recording.evaluation_enabled, rate: recording.sample_rate,
		recorded: scoredDays, window: answeredDays, reads: [scores.read], from: span.start, open,
		figures: 'quality figures', coveredElsewhere: timedDays, missing: 'scores'
	})]));
	const off = Object.fromEntries(windows.map((open) => [String(open.days), measurementOff({
		enabled: recording.evaluation_enabled, recorded: scoredDays, read: scores.read, open, offered: windows
	})]));
	return {
		cardDays: scores.read.state === 'read' || health.read.state === 'read' ? days : null,
		instruments, reasons, windowDay: day, chart: chartConfig(),
		summarizeBands: summarizeConfig().bands,
		matchThresholds: { high: Math.round(evaluation.band_high_min * 100), low: Math.round(evaluation.band_medium_min * 100) },
		recordingNotes: notes, measurementOff: off,
		recordNotes: recordNotesByWindow([
			{ record: 'article', read: health.read },
			{ record: 'score', read: scores.read, switchedOff: !recording.evaluation_enabled }
		], day, windows),
		throughputReference: `${repo}/blob/main/docs/architecture/summarize/throughput.md`,
		faithfulnessReference: `${repo}/blob/main/docs/architecture/publishing/autotune-summary-quality.md`
	};
}
