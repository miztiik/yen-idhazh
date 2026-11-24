<script lang="ts">
	import { daysBetween, type TimeWindow } from '$lib/charts/viewport';
	import { exactJudgeDay, type JudgeIdentity, type JudgeReading } from '$lib/console/judge-observations';
	import { inTrialRange, judgeTrialRange, useJudgeTrialAnswer } from '$lib/console/judge-trial-read.svelte';
	import { judgeCutoffTrialQuery, judgeDrawTrialQuery } from '$lib/console/queries/judgement';
	import { sliceOnce } from '$lib/console/queries/window';
	import { rowsOf } from '$lib/console/voices/record';
	import type { LedgerReach, Row } from '$lib/data/ledger';
	import type { ChartConfig, ConsoleConfig } from '$lib/server/config';
	import JudgeDrawIntervals from './JudgeDrawIntervals.svelte';
	import JudgePairEvidence from './JudgePairEvidence.svelte';

	let { viewport, calendar, reach, readings, selected, identity, detail, binCount, thin, chart, knobs, onPick }: {
		viewport: TimeWindow; calendar: readonly string[]; reach: LedgerReach; readings: ReadonlyMap<string, JudgeReading>;
		selected: string; identity: JudgeIdentity | null; detail: Row | null; binCount: number; thin: number;
		chart: ChartConfig; knobs: ConsoleConfig; onPick: (date: string) => void;
	} = $props();

	const scope = $derived(judgeTrialRange(viewport, daysBetween(viewport.start, viewport.end), reach));
	const draws = useJudgeTrialAnswer(judgeDrawTrialQuery, () => scope, (range) => sliceOnce(judgeDrawTrialQuery, range));
	const cutoff = useJudgeTrialAnswer(judgeCutoffTrialQuery, () => identity !== null && inTrialRange(scope, selected)
		? judgeTrialRange({ start: selected, end: selected }, knobs.default_window_days, reach) : null,
		(range) => sliceOnce(judgeCutoffTrialQuery, range));
	const rowsByDate = $derived.by(() => {
		const rows = new Map<string, Row>();
		const answer = rowsOf(draws.answer);
		const exact = new Map([...readings.values()].map(({ identity }) => [identity.date, identity]));
		for (const row of answer) {
			if (typeof row.date !== 'string') continue;
			const identity = exact.get(row.date);
			if (identity && row.run_id === identity.run && row.attempt === identity.attempt) rows.set(row.date, row);
		}
		return rows;
	});
	const ranking = $derived(identity ? exactJudgeDay(rowsOf(cutoff.answer), identity) : null);
</script>

<JudgeDrawIntervals {calendar} {selected} rows={rowsByDate} fit={ranking} answer={draws.answer}
	{reach} {knobs} {chart} {onPick} onRetry={draws.retry} />
<JudgePairEvidence {viewport} {reach} {readings} {selected} {detail} {ranking} {binCount} {thin} {chart} {knobs} {onPick} />
