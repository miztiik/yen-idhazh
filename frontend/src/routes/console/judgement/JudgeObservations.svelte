<script lang="ts">
	/** Hold one digest across the three panels and read only that attempt's details. */
	import { onMount, type Snippet } from 'svelte';
	import PanelGroup from '$lib/components/PanelGroup.svelte';
	import RouteStatus from '$lib/components/RouteStatus.svelte';
	import { daysInWindow, type TimeWindow } from '$lib/charts/viewport';
	import { judgeCanaries } from '$lib/console/judge-canaries';
	import {
		exactJudgeDay, judgeDayAbsence, judgeModelRule, judgeRange, latestJudgeReadings, matchesJudgeAttempt,
		recordedJudgeModel, selectedJudgeDate,
		type JudgeIdentity, type JudgeReading
	} from '$lib/console/judge-observations';
	import { judgeDayQuery, judgeDrawTrialQuery, judgeHistoryQuery } from '$lib/console/queries/judgement';
	import { useJudgeTrialAnswer } from '$lib/console/judge-trial-read.svelte';
	import { routeReach, retryAsks, sliceOnce } from '$lib/console/queries/window';
	import type { ConsolePanelGroup, judgeObservationRules } from '$lib/console/route-console';
	import { evidenceOf, rowsOf, stateOf, type Answer } from '$lib/console/voices/record';
	import type { LedgerReach, Row } from '$lib/data/ledger';
	import { readSession } from '$lib/data/read-session';
	import { longDate } from '$lib/format';
	import type { ChartConfig, ConsoleConfig } from '$lib/server/config';
	import JudgeCanaryChart from './JudgeCanaryChart.svelte';
	import JudgeCoverage from './JudgeCoverage.svelte';
	import JudgeDigestDetails from './JudgeDigestDetails.svelte';
	import JudgePoolHistogram from './JudgePoolHistogram.svelte';
	import JudgeScoreRanges from './JudgeScoreRanges.svelte';
	import JudgeVisualTrial from './JudgeVisualTrial.svelte';
	import PairScoreDrift from './PairScoreDrift.svelte';

	let { viewport, windowDays, group, rules, knobs, chart, published }: {
		viewport: TimeWindow;
		windowDays: number;
		group: ConsolePanelGroup;
		rules: ReturnType<typeof judgeObservationRules>;
		knobs: ConsoleConfig;
		chart: ChartConfig;
		published: Snippet;
	} = $props();

	let ready = $state(false);
	let held = $state<string | null>(null);
	let historyRetry = $state(0);
	let detailRetry = $state(0);
	let history = $state.raw<{
		viewport: TimeWindow; reach: LedgerReach; answer: Answer; readings: ReadonlyMap<string, JudgeReading>
	} | null>(null);
	let day = $state.raw<{ identity: JudgeIdentity; answer: Answer; row: Row | null } | null>(null);

	const calendar = $derived(daysInWindow(viewport));
	const current = $derived(history?.viewport === viewport ? history : null);
	const reach = $derived(current?.reach ?? null);
	const through = $derived(reach?.state === 'ok' ? reach.through : null);
	const historyAnswer = $derived(current?.answer ?? 'pending');
	const noReadings = new Map<string, JudgeReading>();
	const readings = $derived(current?.readings ?? noReadings);
	const selected = $derived(selectedJudgeDate(calendar, held, readings));
	const selectedReading = $derived(readings.get(selected));
	const model = $derived(recordedJudgeModel(selectedReading));
	const modelRule = $derived(judgeModelRule(calendar, readings));
	const modelChange = $derived(modelRule.changes.at(-1));
	const identity = $derived(selectedReading?.identity ?? null);
	const legacyCanaries = $derived(rules.trialBins == null && selectedReading ? judgeCanaries(selectedReading.cells) : null);
	const detailAnswer = $derived(identity !== null && day?.identity === identity ? day.answer : 'pending');
	const detail = $derived(day?.identity === identity ? day.row : null);
	const historyState = $derived(stateOf(historyAnswer));
	const detailState = $derived(identity !== null ? stateOf(detailAnswer) :
		historyState === 'quiet' ? 'ready' : historyState);
	const answers = $derived(identity === null ? [historyAnswer] : [historyAnswer, detailAnswer]);
	const notes = $derived(evidenceOf(historyAnswer, reach === null ? null : judgeRange(viewport, reach)));
	const noteFor = (date: string) => judgeDayAbsence(date, historyAnswer, reach);
	const dayNote = $derived(identity === null ? noteFor(selected) : judgeDayAbsence(selected, detailAnswer, reach));
	const drawHistory = useJudgeTrialAnswer(judgeDrawTrialQuery, () => {
		const packed = reach;
		if (rules.trialBins == null || packed === null) return null;
		return packed.state === 'ok' ? judgeRange(viewport, packed) ?? { state: 'quiet' } : packed;
	}, (range) => sliceOnce(judgeDrawTrialQuery, range));
	const drawRows = $derived.by(() => {
		const matched = new Map<string, Row>();
		for (const row of rowsOf(drawHistory.answer)) {
			if (typeof row.date !== 'string') continue;
			const reading = readings.get(row.date);
			if (reading && matchesJudgeAttempt(row, reading.identity)) matched.set(row.date, row);
		}
		return matched;
	});

	onMount(() => { ready = true; });

	$effect(() => {
		const window = viewport;
		void historyRetry;
		if (!ready) return;
		let active = true;
		const session = readSession();
		history = null;
		async function load() {
			const result = await routeReach([judgeHistoryQuery.ledger]);
			if (!active || session !== readSession()) return;
			const packed = result.ledgers[judgeHistoryQuery.ledger]!;
			const range = judgeRange(window, packed);
			const answer = range === null ? packed.state === 'ok' ? { state: 'quiet' } as const : packed
				: await sliceOnce(judgeHistoryQuery, range);
			if (!active || session !== readSession()) return;
			const readings = latestJudgeReadings(rowsOf(answer));
			if (answer.state === 'ok' || answer.state === 'quiet') {
				held = selectedJudgeDate(daysInWindow(window), held, readings);
			}
			history = { viewport: window, reach: packed, answer, readings };
		}
		void load().catch((error: unknown) => {
			if (!active || session !== readSession()) return;
			console.warn('[judgement] The packed observations could not be read.', error);
			const unavailable = { state: 'unreachable' } as const;
			history = { viewport: window, reach: unavailable, answer: unavailable, readings: noReadings };
		});
		return () => { active = false; };
	});

	$effect(() => {
		const picked = identity;
		void detailRetry;
		day = null;
		if (picked === null) return;
		let active = true;
		const session = readSession();
		const { date } = picked;
		function unavailable() {
			day = { identity: picked!, answer: { state: 'unreachable', at: date, fault: null }, row: null };
		}
		void sliceOnce(judgeDayQuery, { from: date, to: date, days: 1, asked: 1 }).then((answer) => {
			if (!active || session !== readSession()) return;
			const row = exactJudgeDay(rowsOf(answer), picked);
			if (row === null && (answer.state === 'ok' || answer.state === 'quiet')) {
				console.warn('[judgement] The selected run and attempt are not in the packed digest.');
				unavailable();
			} else {
				day = { identity: picked, answer, row };
			}
		}).catch((error: unknown) => {
			if (!active || session !== readSession()) return;
			console.warn('[judgement] The selected digest could not be read.', error);
			unavailable();
		});
		return () => { active = false; };
	});

	function pick(date: string) {
		if (calendar.includes(date)) held = date;
	}
	function retry() {
		if (historyState === 'unreachable') {
			retryAsks([judgeHistoryQuery]);
			historyRetry++;
		}
		if (detailState === 'unreachable' && identity !== null) {
			retryAsks([judgeDayQuery]);
			detailRetry++;
		}
	}
</script>

<RouteStatus route="judgement" {answers} days={windowDays} {through} recordScope={group.title}
	shimmerAfterMs={knobs.shimmer_after_ms} onRetry={retry}>
	{@render published()}
	<PanelGroup id={group.id} title={group.title} panels={group.panels.length}>
		<div class="digest-control">
			<label>
				Selected digest (UTC)
				<select value={selected} disabled={historyState === 'loading'} onchange={(event) => pick(event.currentTarget.value)}>
					{#each calendar as date (date)}<option value={date}>{longDate(date)}</option>{/each}
				</select>
			</label>
			{#if selectedReading}
				<p>Judge model for selected digest: <strong>{model ?? 'Not recorded'}</strong></p>
			{/if}
			{#if modelChange}
				<p>{modelChange.words}. First observed on the {longDate(modelChange.date)} UTC digest.</p>
			{/if}
			{#each notes as note}<p>{note}</p>{/each}
		</div>
		{#each group.panels as id (id)}
			{#if id === 'judge-coverage'}
				<JudgeCoverage {calendar} {windowDays} {readings} {selected} {detail} {historyState} rule={modelRule}
					trialDraws={rules.trialBins == null ? null : drawRows} {dayNote} {noteFor} {knobs} {chart} onPick={pick} />
			{:else if id === 'judge-score-ranges'}
				<JudgeScoreRanges {selected} {detail} {detailState} {dayNote} thin={rules.thin} {knobs} {chart}
					trial={rules.trialBins != null} />
				{#if rules.trialBins != null && reach !== null}
					<JudgeVisualTrial {viewport} {calendar} {reach} {readings} {selected} {identity} {detail}
						{drawRows} drawAnswer={drawHistory.answer} onDrawRetry={drawHistory.retry}
						binCount={rules.trialBins} contextShare={rules.trialContextShare} thin={rules.thin} {chart} {knobs} onPick={pick} />
				{/if}
			{:else if id === 'pair-score-drift'}
				{#if rules.trialBins != null && reach !== null}
					<JudgePoolHistogram {viewport} {reach} {selected} {identity} {detail} {chart} {knobs} />
				{/if}
				<PairScoreDrift {calendar} {windowDays} {readings} {selected} {detail} {historyState} {dayNote}
					{noteFor} low={rules.low} high={rules.high} {knobs} {chart} onPick={pick} />
			{/if}
		{/each}
		{#if rules.trialBins != null}
			<JudgeCanaryChart {calendar} {selected} {readings} {noteFor} {knobs} {chart} onPick={pick} />
		{/if}
		<JudgeDigestDetails {selected} {identity} {detail} {dayNote} {chart} canaries={legacyCanaries} />
	</PanelGroup>
</RouteStatus>

<style>
	.digest-control {
		grid-column: 1 / -1;
		display: grid;
		justify-items: start;
		gap: var(--space-2);
		font-size: var(--console-small-size);
		line-height: var(--console-small-leading);
	}
	.digest-control p {
		margin: 0;
		color: var(--color-text-secondary);
		overflow-wrap: anywhere;
	}
	label {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-2);
	}
	select {
		max-inline-size: 100%;
		min-block-size: var(--console-control-min-height);
		padding-inline: var(--console-control-padding-inline);
		border: 1px solid var(--color-rule-strong);
		border-radius: var(--console-control-radius);
		background: var(--color-surface);
		color: var(--color-text);
		font: inherit;
	}
	select:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
</style>
