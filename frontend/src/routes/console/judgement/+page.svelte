<script lang="ts">
	/** Which stories the day merged, and what the judge and hand marks can tell us. */
	import { base } from '$app/paths';
	import { onMount } from 'svelte';
	import { windowOfDays } from '$lib/charts/viewport';
	import { consoleKnobs } from '$lib/console/route-console';
	import { markedApart, scoreRange } from '$lib/console/holdout';
	import WindowControlSource from '$lib/components/WindowControlSource.svelte';
	import MergeLinePlot from './MergeLinePlot.svelte';
	import MergedStoriesPanel from './MergedStoriesPanel.svelte';
	import HoldoutMargin from './HoldoutMargin.svelte';
	import JudgeAgreement from './JudgeAgreement.svelte';
	import RecordGates from './RecordGates.svelte';
	import VerdictSplit from './VerdictSplit.svelte';

	let { data } = $props();
	const console = consoleKnobs();

	/** The same key the other four console routes read, so the operator's choice
	 * of span follows him between them rather than resetting on every click. */
	const WINDOW_KEY = 'idhazh:console-window';

	const presets = console.window_presets;

	// svelte-ignore state_referenced_locally
	let windowDays = $state(console.default_window_days);
	/** False until a browser has run this page. The control cannot do anything
	 * before that, so it says so rather than pretending. */
	let ready = $state(false);

	onMount(() => {
		ready = true;
		if (typeof localStorage === 'undefined') return;
		const stored = Number(localStorage.getItem(WINDOW_KEY));
		if (presets.includes(stored) && stored !== windowDays) show(stored);
	});

	function show(days: number, remember = true) {
		windowDays = days;
		if (remember && typeof localStorage !== 'undefined') {
			localStorage.setItem(WINDOW_KEY, String(days));
		}
	}

	/** Nothing on this route is fetched. Every span it can draw is already
	 * inlined, so no preset costs a month file and none of them is priced. */
	function monthsFor(): number {
		return 0;
	}

	const viewport = $derived(
		windowOfDays(data.windowDay, windowDays, console.today_anchor)
	);

	/** Where the pairs a person read as two stories sit, for the one chart on
	 * this route that has a date axis to draw the line walking into them. */
	const apartSpan = $derived(markedApart(data.holdout.marks));
	const apartAt = $derived(scoreRange(apartSpan.map((mark) => mark.score)));
</script>

<svelte:head>
	<title>Judgement &mdash; Console &mdash; {data.ui.site_title}</title>
</svelte:head>

<div data-console-panels="judgement">
	<!-- The title, the strip, the band and the days control are the shell and
	     live in `../+layout.svelte`. The window stays here because it governs
	     this route's panels and nothing above them, and this hands it up. -->
	<WindowControlSource days={windowDays} {presets} {monthsFor} {ready} onChange={show} />

	<p class="console-carry" data-console-carry="model">
		{data.carries.judgement}
		<a class="carry-link" href="{base}/console/model/">Summaries &rarr;</a>
	</p>

	<MergedStoriesPanel
		days={data.merges}
		{viewport}
		height={console.chart_height}
		width={console.chart_width}
		tickDensity={data.chart.tick_density}
		readoutMaxShare={data.chart.readout_max_share}
	/>

	<MergeLinePlot
		days={data.lines}
		knobs={data.similarity}
		{viewport}
		height={console.chart_height}
		width={console.chart_width}
		tickDensity={data.chart.tick_density}
		readoutMaxShare={data.chart.readout_max_share}
		builtWith={data.builtWith}
		markedApart={apartAt === null
			? null
			: { low: apartAt.min, high: apartAt.max, count: apartSpan.length }}
	/>

	<JudgeAgreement
		days={data.judge}
		limits={{
			disagreementMax: data.similarity.disagreement_max,
			unclearMax: data.similarity.unclear_max
		}}
		{viewport}
		height={console.chart_height}
		width={console.chart_width}
		tickDensity={data.chart.tick_density}
		readoutMaxShare={data.chart.readout_max_share}
		attemptsFloor={console.min_attempts_for_rate}
	/>

	<RecordGates
		days={data.judge}
		dates={data.span}
		gates={{
			minimumNegatives: data.similarity.minimum_negatives,
			minimumDays: data.similarity.minimum_days,
			minimumAboveLine: data.similarity.minimum_above_line
		}}
		{viewport}
		readoutMaxShare={data.chart.readout_max_share}
	/>

	<VerdictSplit
		record={data.record}
		applied={data.builtWith}
		discardShare={data.similarity.discard_share}
		axisMultiple={console.precision_axis_multiple}
		width={console.chart_width}
		figures={data.figures}
	/>

	<HoldoutMargin
		marks={data.holdout.marks}
		agreedScores={data.holdout.agreedScores}
		skipped={data.holdout.skipped}
		marked={data.holdout.marked}
		applied={data.builtWith}
		maxDownStep={data.similarity.max_down_bins * data.similarity.bin_width}
		fitted={data.lines.length > 0}
		weights={data.holdout.weights}
		scored={data.holdout.scored}
		height={console.chart_height}
		width={console.chart_width}
		readoutMaxShare={data.chart.readout_max_share}
	/>

</div>
