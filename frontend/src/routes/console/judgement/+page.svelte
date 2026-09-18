<script lang="ts">
	/** What the model made of each article - the route, and the first fact on it.
	 *
	 * **The panel and the named absence sit side by side on purpose.** The strip
	 * took a fourth and a fifth tab on 2026-09-12 and this route opened empty
	 * behind one of them, so it answered 200 and printed an absence saying what
	 * was still missing. `Stories the day merged` is the first figure to land
	 * here, and it does not close that absence: it counts what a day folded
	 * together, and the absence is about the desk and the lenses the model chose.
	 * So the figure is drawn and the absence is still named.
	 *
	 * The control governs the panels below it, which is why the route has one now
	 * and had none before. Nothing here is fetched: every span the control can
	 * draw is already in this document, so a preset costs no request.
	 */
	import { base } from '$app/paths';
	import { onMount } from 'svelte';
	import { windowOfDays } from '$lib/charts/viewport';
	import WindowControl from '$lib/components/WindowControl.svelte';
	import MergeLinePlot from './MergeLinePlot.svelte';
	import MergedStoriesPanel from './MergedStoriesPanel.svelte';
	import JudgeAgreement from './JudgeAgreement.svelte';
	import RecordGates from './RecordGates.svelte';
	import VerdictSplit from './VerdictSplit.svelte';

	let { data } = $props();

	/** The same key the other four console routes read, so the operator's choice
	 * of span follows him between them rather than resetting on every click. */
	const WINDOW_KEY = 'idhazh:console-window';

	const presets = $derived(data.console.window_presets);

	// svelte-ignore state_referenced_locally
	let windowDays = $state(data.console.default_window_days);
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
		windowOfDays(
			data.merges.map((day) => day.date),
			data.today,
			windowDays,
			data.console.today_anchor
		)
	);
</script>

<div data-console-panels="judgement">
	<!-- The title, the strip and the band are the shell and live in
	     `../+layout.svelte`. The control stays here because it governs this
	     route's panels and nothing above them. -->
	<WindowControl days={windowDays} {presets} {monthsFor} {ready} onChange={show} />

	<p class="console-carry" data-console-carry="model">
		{data.carries.judgement}
		<a class="carry-link" href="{base}/console/model/">Summaries &rarr;</a>
	</p>

	<MergedStoriesPanel
		days={data.merges}
		{viewport}
		height={data.console.chart_height}
		width={data.console.chart_width}
		tickDensity={data.chart.tick_density}
	/>

	<MergeLinePlot
		days={data.lines}
		knobs={data.similarity}
		{viewport}
		height={data.console.chart_height}
		width={data.console.chart_width}
		tickDensity={data.chart.tick_density}
		readoutMaxShare={data.chart.readout_max_share}
		configuredLine={data.configuredLine}
	/>

	<JudgeAgreement
		days={data.judge}
		limits={{
			disagreementMax: data.similarity.disagreement_max,
			unclearMax: data.similarity.unclear_max
		}}
		{viewport}
		height={data.console.chart_height}
		width={data.console.chart_width}
		tickDensity={data.chart.tick_density}
		readoutMaxShare={data.chart.readout_max_share}
		attemptsFloor={data.console.min_attempts_for_rate}
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
	/>

	<VerdictSplit
		record={data.record}
		applied={data.lines.at(-1)?.applied ?? data.configuredLine}
		discardShare={data.similarity.discard_share}
		axisMultiple={data.console.precision_axis_multiple}
		width={data.console.chart_width}
		figures={data.figures}
	/>

	<h2 class="console-h2">What the model made of each article</h2>

	<div class="console-panel" data-console-empty="judgement">
		<p class="empty-lead">
			This route will carry what the model made of each article: the desk and the
			lenses it chose, how sure it was of each, and every article where its answer
			and ours differ.
		</p>
		<p class="empty-note">
			The panel above counts what a day folded together, which is a fact about what
			shipped. What the model chose is not drawn here yet: it does not record the
			desk and lenses it picked or how sure it was, and the panels that would draw
			them are not built. Until both arrive, what the checker doubted is on
			Summaries.
		</p>
	</div>
</div>

<style>
	/* The lead carries the weight of the absence, and the note under it is the
	   secondary voice every console panel uses for a caveat (design-system.md). */
	.empty-lead {
		margin: 0;
		font-size: var(--text-base);
		line-height: var(--leading-base);
		color: var(--color-text);
	}

	.empty-note {
		margin: var(--space-3) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}
</style>
