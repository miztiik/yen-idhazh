<script lang="ts">
	/** Which stories the day merged, and what the judge and hand marks can tell us. */
	import { onMount } from 'svelte';
	import { useWindowChoice } from '$lib/console/window-slot';
	import { windowFromDates, windowOfDays } from '$lib/charts/viewport';
	import { consoleKnobs, routeConsole } from '$lib/console/route-console';
	import { markedApart, scoreRange } from '$lib/console/holdout';
	import { judgementEvidence } from '$lib/console/judgement-evidence';
	import WindowControlSource from '$lib/components/WindowControlSource.svelte';
	import PanelGroup from '$lib/components/PanelGroup.svelte';
	import MergeLinePlot from './MergeLinePlot.svelte';
	import MergedStoriesPanel from './MergedStoriesPanel.svelte';
	import HoldoutMargin from './HoldoutMargin.svelte';
	import JudgeAgreement from './JudgeAgreement.svelte';
	import RecordGates from './RecordGates.svelte';
	import VerdictSplit from './VerdictSplit.svelte';

	let { data } = $props();
	const console = consoleKnobs();
	const configured = routeConsole('judgement');

	const presets = console.window_presets;
	const choice = useWindowChoice();
	const windowDays = $derived(choice.days);
	/** False until a browser has run this page. The control cannot do anything
	 * before that, so it says so rather than pretending. */
	let ready = $state(false);

	onMount(() => {
		ready = true;
	});

	function show(days: number) {
		choice.select(days);
	}

	/** Nothing on this route is fetched. Every span it can draw is already
	 * inlined, so no preset costs a month file and none of them is priced. */
	function monthsFor(): number {
		return 0;
	}

	const publishedWindow = $derived(windowFromDates(data.merges.map((day) => day.date), windowDays));
	const viewport = $derived(publishedWindow ?? windowOfDays(data.windowDay, windowDays, 'right'));
	const judgeWindow = $derived(windowFromDates(data.fittedRead.state === 'read'
		? [data.fittedRead.first, data.fittedRead.through] : [], windowDays));
	const judgeViewport = $derived(judgeWindow ?? viewport);
	const judgeRecord = $derived(data.fittedRead.state === 'read'
		? { asked: windowDays, first: data.fittedRead.first, through: judgeWindow?.end ?? null } : null);

	/** Where the pairs a person read as two stories sit, for the one chart on
	 * this route that has a date axis to draw the line walking into them. */
	const apartSpan = $derived(markedApart(data.holdout.marks));
	const apartAt = $derived(scoreRange(apartSpan.map((mark) => mark.score)));
	const rejectedJudgeRows = $derived(data.rejectedJudgeRows.filter((row) => row.date >= judgeViewport.start && row.date <= judgeViewport.end));
	const judgeNotes = $derived([
		...judgementEvidence(data.fittedRead, judgeViewport, data.readSpan, 'judge'),
		...rejectedJudgeRows.map((row) => row.rates
			? `The judge's rate readings on ${row.date} are unavailable. They cannot support a complete window verdict.`
			: `The calculated-line or gate readings on ${row.date} are unavailable. Valid judge-rate readings remain visible.`)
	]);
	const markNotes = $derived(judgementEvidence(data.holdout.read, data.holdout.reach, data.holdout.reach, 'marks'));
	const scoreNotes = $derived(judgementEvidence(data.holdout.scoredRead, data.readSpan, data.readSpan, 'scores'));
</script>

<svelte:head>
	<title>Judgement &mdash; Console &mdash; {data.ui.site_title}</title>
</svelte:head>

<div data-console-panels="judgement">
	<!-- The route owns its evidence window and hands the control to the shared shell. -->
	<WindowControlSource route="judgement" days={windowDays} {presets} {monthsFor} {ready}
		{publishedWindow} record={judgeRecord} onChange={show} />

	{#each configured.panel_groups as group (group.id)}
		<PanelGroup id={group.id} title={group.title} panels={group.panels.length}>
			{#each group.panels as id (id)}
	{#if id === 'merged-stories'}
	<MergedStoriesPanel
		days={data.merges}
		{viewport}
		height={console.chart_height}
		width={console.chart_width}
		tickDensity={data.chart.tick_density}
		readoutMaxShare={data.chart.readout_max_share}
	/>

	{:else if id === 'merge-line'}
	<MergeLinePlot
		days={data.fittedRead.state === 'read' ? data.lines : null}
		evidence={judgeNotes}
		knobs={data.similarity}
		viewport={judgeViewport}
		height={console.chart_height}
		width={console.chart_width}
		tickDensity={data.chart.tick_density}
		readoutMaxShare={data.chart.readout_max_share}
		builtWith={data.builtWith}
		markedApart={apartAt === null
			? null
			: { low: apartAt.min, high: apartAt.max, count: apartSpan.length }}
	/>

	{:else if id === 'judge-agreement'}
	<JudgeAgreement
		days={data.fittedRead.state === 'read' ? data.judgeRates : null}
		complete={!rejectedJudgeRows.some((row) => row.rates)}
		evidence={judgeNotes}
		limits={{
			disagreementMax: data.similarity.disagreement_max,
			unclearMax: data.similarity.unclear_max
		}}
		viewport={judgeViewport}
		height={console.chart_height}
		width={console.chart_width}
		tickDensity={data.chart.tick_density}
		readoutMaxShare={data.chart.readout_max_share}
		attemptsFloor={console.min_attempts_for_rate}
	/>

	{:else if id === 'record-gates'}
	<RecordGates
		days={data.fittedRead.state === 'read' ? data.judge : null}
		evidence={judgeNotes}
		dates={data.span}
		gates={{
			minimumNegatives: data.similarity.minimum_negatives,
			minimumDays: data.similarity.minimum_days,
			minimumAboveLine: data.similarity.minimum_above_line
		}}
		viewport={judgeViewport}
		readoutMaxShare={data.chart.readout_max_share}
	/>

	{:else if id === 'verdict-split'}
	<VerdictSplit
		evidence={judgeNotes}
		record={data.record}
		applied={data.builtWith}
		discardShare={data.similarity.discard_share}
		axisMultiple={console.precision_axis_multiple}
		width={console.chart_width}
		figures={data.figures}
	/>

	{:else if id === 'holdout-margin'}
	<HoldoutMargin
		marks={data.holdout.read.state === 'read' ? data.holdout.marks : null}
		agreedScores={data.holdout.read.state === 'read' ? data.holdout.agreedScores : null}
		evidence={[...markNotes, ...scoreNotes]}
		skipped={data.holdout.skipped}
		marked={data.holdout.marked}
		applied={data.builtWith}
		maxDownStep={data.similarity.max_down_bins * data.similarity.bin_width}
		fitted={data.lines.some((row) => row.heldReason === 'none')}
		weights={data.holdout.weights}
		scored={data.holdout.scored}
		height={console.chart_height}
		width={console.chart_width}
		readoutMaxShare={data.chart.readout_max_share}
	/>
	{/if}
			{/each}
		</PanelGroup>
	{/each}

</div>
