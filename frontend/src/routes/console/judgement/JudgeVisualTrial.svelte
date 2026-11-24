<script lang="ts">
	import { daysBetween, type TimeWindow } from '$lib/charts/viewport';
	import { exactJudgeDay, type JudgeIdentity, type JudgeReading } from '$lib/console/judge-observations';
	import { inTrialRange, judgeTrialRange, useJudgeTrialAnswer } from '$lib/console/judge-trial-read.svelte';
	import { judgeCutoffTrialQuery } from '$lib/console/queries/judgement';
	import { sliceOnce } from '$lib/console/queries/window';
	import { rowsOf, type Answer } from '$lib/console/voices/record';
	import type { LedgerReach, Row } from '$lib/data/ledger';
	import type { ChartConfig, ConsoleConfig } from '$lib/server/config';
	import JudgeDrawIntervals from './JudgeDrawIntervals.svelte';
	import JudgePairEvidence from './JudgePairEvidence.svelte';

	let { viewport, calendar, reach, readings, selected, identity, detail, drawRows, drawAnswer, onDrawRetry,
		binCount, thin, contextShare, chart, knobs, onPick }: {
		viewport: TimeWindow; calendar: readonly string[]; reach: LedgerReach; readings: ReadonlyMap<string, JudgeReading>;
		selected: string; identity: JudgeIdentity | null; detail: Row | null; binCount: number; thin: number;
		drawRows: ReadonlyMap<string, Row>; drawAnswer: Answer; onDrawRetry: () => void; contextShare: number | null;
		chart: ChartConfig; knobs: ConsoleConfig; onPick: (date: string) => void;
	} = $props();

	const scope = $derived(judgeTrialRange(viewport, daysBetween(viewport.start, viewport.end), reach));
	const cutoff = useJudgeTrialAnswer(judgeCutoffTrialQuery, () => identity !== null && inTrialRange(scope, selected)
		? judgeTrialRange({ start: selected, end: selected }, knobs.default_window_days, reach) : null,
		(range) => sliceOnce(judgeCutoffTrialQuery, range));
	const ranking = $derived(identity ? exactJudgeDay(rowsOf(cutoff.answer), identity) : null);
</script>

<JudgeDrawIntervals {calendar} {selected} rows={drawRows} fit={ranking} answer={drawAnswer}
	{reach} {knobs} {chart} {contextShare} {onPick} onRetry={onDrawRetry} />
<JudgePairEvidence {viewport} {reach} {readings} {selected} {detail} {ranking} {binCount} {thin} {chart} {knobs} {onPick} />
