<script lang="ts">
	import { datesOf, evidenceOf, rowsOf } from '$lib/console/voices/record';
	import type { TimeWindow } from '$lib/charts/viewport';
	import { judgeDayAbsence, type JudgeReading } from '$lib/console/judge-observations';
	import { judgePairDays, judgeScoreBands, type PairDay } from '$lib/console/judge-pair-evidence';
	import { inTrialRange, judgeTrialRange, revealJudgeTrial, useJudgeTrialAnswer } from '$lib/console/judge-trial-read.svelte';
	import { judgePairTrialQuery } from '$lib/console/queries/judgement';
	import { routeReach, sliceOnce } from '$lib/console/queries/window';
	import type { LedgerReach, Row } from '$lib/data/ledger';
	import { readSession } from '$lib/data/read-session';
	import type { ChartConfig, ConsoleConfig } from '$lib/server/config';
	import JudgeCutoffDiagnostics from './JudgeCutoffDiagnostics.svelte';
	import JudgeVerdictHeatmaps from './JudgeVerdictHeatmaps.svelte';

	let { viewport, reach, readings, selected, detail, ranking, binCount, thin, chart, knobs, onPick }: {
		viewport: TimeWindow; reach: LedgerReach; readings: ReadonlyMap<string, JudgeReading>;
		selected: string; detail: Row | null; ranking: Row | null; binCount: number; thin: number;
		chart: ChartConfig; knobs: ConsoleConfig; onPick: (date: string) => void;
	} = $props();

	let near = $state(false);
	let reachRetry = $state(0);
	let pairReach = $state.raw<LedgerReach | null>(null);
	$effect(() => {
		void reachRetry;
		if (!near) return;
		const session = readSession();
		let active = true;
		pairReach = null;
		void routeReach([judgePairTrialQuery.ledger]).then(({ ledgers }) => {
			if (active && session === readSession()) pairReach = ledgers[judgePairTrialQuery.ledger] ?? { state: 'missing', fault: 'not-packed' };
		}, (error: unknown) => {
			if (!active || session !== readSession()) return;
			console.warn('[judgement] The packed pair reach could not be read.', error);
			pairReach = { state: 'unreachable' };
		});
		return () => { active = false; };
	});

	const request = $derived(pairReach === null ? null : judgeTrialRange(viewport, knobs.default_window_days, reach, pairReach));
	const span = $derived(request !== null && 'from' in request ? request : null);
	const inWindow = $derived(inTrialRange(request, selected));
	const history = useJudgeTrialAnswer(judgePairTrialQuery, () => request, (range) => sliceOnce(judgePairTrialQuery, range));
	const day = useJudgeTrialAnswer(judgePairTrialQuery, () => pairReach !== null && !inWindow && readings.has(selected)
		? judgeTrialRange({ start: selected, end: selected }, knobs.default_window_days, reach, pairReach) : null,
		(range) => sliceOnce(judgePairTrialQuery, range));
	const historyDays = $derived(judgePairDays(rowsOf(history.answer), readings));
	const selectedAnswer = $derived(inWindow || !readings.has(selected) ? history.answer : day.answer);
	const exactDay = $derived(inWindow ? historyDays.get(selected) : judgePairDays(rowsOf(day.answer), readings).get(selected));
	const dates = $derived(span === null ? [] : datesOf(span));
	const bands = $derived(judgeScoreBands(binCount));
	const notes = $derived(evidenceOf(history.answer, span));
	const invalid = (outcome: PairDay | undefined) => outcome?.state === 'invalid' ? 'Did not arrive as a valid exact-attempt pair set.'
		: outcome?.state === 'incomplete' ? 'Did not arrive: recorded pairs do not match the saved return count.' : null;
	const dayNote = (date: string) => invalid(historyDays.get(date)) ?? judgeDayAbsence(date, history.answer, pairReach);
	const status = $derived(history.answer === 'pending' ? 'Loading recorded pair verdicts...'
		: history.answer.state === 'ok' ? null : history.answer.state === 'quiet' ? 'No recorded pair verdicts in this span.'
			: judgeDayAbsence(selected, history.answer, pairReach));
	const selectedStatus = $derived(invalid(exactDay) ?? judgeDayAbsence(selected, selectedAnswer, pairReach));
	const failed = $derived([history.answer, day.answer].some((answer) => answer !== 'pending' && answer.state === 'unreachable'));

	function retry() {
		if (pairReach?.state === 'unreachable') reachRetry++;
		history.retry();
		day.retry();
	}
</script>

<div class="pair-trial" use:revealJudgeTrial={() => near = true}>
	<JudgeVerdictHeatmaps {dates} {bands} days={historyDays} {selected} {status} {thin} {chart} {onPick} noteFor={dayNote} />
	{#each notes as note}<p>{note}</p>{/each}
	{#if failed}<button type="button" onclick={retry}>Retry recorded pair verdicts</button>{/if}
	<JudgeCutoffDiagnostics {selected} day={exactDay} status={selectedStatus} {detail} {ranking} {chart} {knobs} />
</div>

<style>
	.pair-trial { grid-column: 1 / -1; min-inline-size: 0; }
	.pair-trial > p { margin-block: var(--space-2); color: var(--color-text-secondary); }
</style>
