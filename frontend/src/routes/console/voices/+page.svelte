<script lang="ts">
	/** What did sources supply, and what did the ranking do with their articles? */
	import { onMount } from 'svelte';
	import { base } from '$app/paths';
	import { consoleKnobs, routeConsole, routeKnobs } from '$lib/console/route-console';
	import { rangeFor, routeReach, sliceOnce, retryAsks, type Range, type RouteReach } from '$lib/console/queries/window';
	import { feedsFailedQuery, fetchTimeQuery, sourceCutsQuery, whyChosenQuery, watchlistQuery } from '$lib/console/queries/voices';
	import { readSession } from '$lib/data/read-session';
	import { evidenceOf, rowsOf, stateOf, type Answer } from '$lib/console/voices/record';
	import { sourceHealth } from '$lib/console/voices/source-health';
	import { rankingDiscount } from '$lib/console/voices/ranking-discount';
	import { retirementDrawing } from '$lib/console/voices/retiring';
	import { feedsFailed, fallbackFeeds, feedReadNotes } from '$lib/console/voices/feeds-failed';
	import { fetchTime } from '$lib/console/voices/fetch-time';
	import { sourceCuts } from '$lib/console/voices/source-cuts';
	import { whyChosen } from '$lib/console/voices/why-chosen';
	import { watchlist } from '$lib/console/voices/watchlist';
	import RouteStatus from '$lib/components/RouteStatus.svelte';
	import WindowControlSource from '$lib/components/WindowControlSource.svelte';
	import PanelGroup from '$lib/components/PanelGroup.svelte';
	import SourceHealthPanel from '$lib/console/voices/SourceHealthPanel.svelte';
	import FeedsFailedPanel from '$lib/console/voices/FeedsFailedPanel.svelte';
	import FetchTimePanel from '$lib/console/voices/FetchTimePanel.svelte';
	import RetiringPanel from '$lib/console/voices/RetiringPanel.svelte';
	import SourceCutsPanel from '$lib/console/voices/SourceCutsPanel.svelte';
	import RankingDiscountPanel from '$lib/console/voices/RankingDiscountPanel.svelte';
	import WhyChosenPanel from '$lib/console/voices/WhyChosenPanel.svelte';
	import WatchlistPanel from '$lib/console/voices/WatchlistPanel.svelte';

	let { data } = $props();
	const console = consoleKnobs();
	const config = routeConsole('voices');
	const knobs = routeKnobs('voices', ['article_fails_marked', 'article_fails_named', 'why_chosen_rows', 'watchlist_hits_marked', 'watchlist_hits_named']);
	const WINDOW_KEY = 'idhazh:console-window';
	let windowDays = $state(console.default_window_days);
	let ready = $state(false);
	let reach = $state<RouteReach | null>(null);
	let feedsAnswer = $state<Answer>('pending');
	let fetchAnswer = $state<Answer>('pending');
	let cutsAnswer = $state<Answer>('pending');
	let chosenAnswer = $state<Answer>('pending');
	let watchAnswer = $state<Answer>('pending');
	let span = $state<Range | null>(null);
	let fetchSpan = $state<Range | null>(null);
	let cutsSpan = $state<Range | null>(null);
	let watchSpan = $state<Range | null>(null);
	let chosenSpan = $state<Range | null>(null);
	let generation = 0;
	let session: symbol | null = null;
	const answers = $derived([feedsAnswer, fetchAnswer, cutsAnswer, chosenAnswer, watchAnswer]);
	const busy = $derived(answers.includes('pending'));
	const census = $derived(sourceHealth(data.sourceView, console.source_rows));
	const discount = $derived(rankingDiscount(data.sourceView, console.source_rows));
	const retirement = $derived(retirementDrawing(data.retiring, data.chart.tick_density));
	const fallback = $derived(fallbackFeeds(data.feedInput, windowDays, console.feed_rows, knobs.article_fails_marked, knobs.article_fails_named));
	const failed = $derived(feedsAnswer !== 'pending' && feedsAnswer.state !== 'ok' ? fallback : span === null ? null : feedsFailed(data.feedInput,
		rowsOf(feedsAnswer), span, console.feed_rows, knobs.article_fails_marked, knobs.article_fails_named));
	const times = $derived(fetchTime(rowsOf(fetchAnswer), console.source_rows, data.number_format));
	const cuts = $derived(cutsSpan === null ? null : sourceCuts(rowsOf(cutsAnswer), cutsSpan, console.source_rows));
	const chosen = $derived(whyChosen(rowsOf(chosenAnswer), knobs.why_chosen_rows));
	const catches = $derived(watchSpan === null ? null : watchlist(rowsOf(watchAnswer), watchSpan, knobs.watchlist_hits_marked, knobs.watchlist_hits_named));
	const feedPanelState = $derived(feedsAnswer === 'pending' ? 'loading' : data.feedInput.read.state === 'not-packed' ? 'missing' :
		data.feedInput.read.state === 'unreadable' ? 'unreachable' :
		(failed && (failed.feedThrough !== null || failed.articleThrough !== null)) || fallback ? 'ready' : stateOf(feedsAnswer));

	onMount(() => {
		ready = true;
		const stored = Number(localStorage.getItem(WINDOW_KEY));
		if (console.window_presets.includes(stored)) windowDays = stored;
		void ask();
	});
	function show(days: number) {
		windowDays = days;
		localStorage.setItem(WINDOW_KEY, String(days));
		void ask();
	}
	async function ask(retry = false) {
		const turn = ++generation;
		const current = readSession();
		if (session !== current) retry = false;
		session = current;
		const needFeeds = !retry || stateOf(feedsAnswer) === 'unreachable';
		const needFetch = !retry || stateOf(fetchAnswer) === 'unreachable';
		const needCuts = !retry || stateOf(cutsAnswer) === 'unreachable';
		const needChosen = !retry || stateOf(chosenAnswer) === 'unreachable';
		const needWatch = !retry || stateOf(watchAnswer) === 'unreachable';
		if (retry) retryAsks([
			...(needFeeds ? [feedsFailedQuery] : []), ...(needFetch ? [fetchTimeQuery] : []),
			...(needCuts ? [sourceCutsQuery] : []), ...(needChosen ? [whyChosenQuery] : []), ...(needWatch ? [watchlistQuery] : [])
		]);
		if (needFeeds) feedsAnswer = 'pending';
		if (needFetch) fetchAnswer = 'pending';
		if (needCuts) cutsAnswer = 'pending';
		if (needChosen) chosenAnswer = 'pending';
		if (needWatch) watchAnswer = 'pending';
		const found = await routeReach(['item-health']);
		if (turn !== generation) return;
		reach = found;
		const f = rangeFor(feedsFailedQuery, windowDays, found, console.window_presets);
		const t = rangeFor(fetchTimeQuery, windowDays, found, console.window_presets);
		const c = rangeFor(sourceCutsQuery, windowDays, found, console.window_presets);
		const y = rangeFor(whyChosenQuery, windowDays, found, console.window_presets);
		const w = rangeFor(watchlistQuery, windowDays, found, console.window_presets);
		if (needFeeds) span = 'from' in f ? f : null;
		if (needFetch) fetchSpan = 'from' in t ? t : null;
		if (needCuts) cutsSpan = 'from' in c ? c : null;
		if (needChosen) chosenSpan = 'from' in y ? y : null;
		if (needWatch) watchSpan = 'from' in w ? w : null;
		await Promise.all([
			needFeeds ? ('from' in f ? sliceOnce(feedsFailedQuery, f) : Promise.resolve(f)).then((answer) => { if (turn === generation) feedsAnswer = answer; }) : null,
			needFetch ? ('from' in t ? sliceOnce(fetchTimeQuery, t) : Promise.resolve(t)).then((answer) => { if (turn === generation) fetchAnswer = answer; }) : null,
			needCuts ? ('from' in c ? sliceOnce(sourceCutsQuery, c) : Promise.resolve(c)).then((answer) => { if (turn === generation) cutsAnswer = answer; }) : null,
			needChosen ? ('from' in y ? sliceOnce(whyChosenQuery, y) : Promise.resolve(y)).then((answer) => { if (turn === generation) chosenAnswer = answer; }) : null,
			needWatch ? ('from' in w ? sliceOnce(watchlistQuery, w) : Promise.resolve(w)).then((answer) => { if (turn === generation) watchAnswer = answer; }) : null
		]);
	}
	function monthsFor(): number { return 0; }
</script>

<svelte:head><title>Voices &mdash; Console &mdash; {data.ui.site_title}</title></svelte:head>
<RouteStatus route="voices" {answers} days={windowDays} through={reach?.through ?? null} shimmerAfterMs={console.shimmer_after_ms} onRetry={() => void ask(true)}>
	<WindowControlSource days={windowDays} presets={console.window_presets} {monthsFor} {busy} {ready}
		record={{ asked: windowDays, first: reach?.ledgers['item-health']?.state === 'ok' ? reach.ledgers['item-health'].first : null, through: reach?.through ?? null }} onChange={show}/>
	<p class="console-carry" data-console-carry="pipelines">{data.carries.voices} <a href="{base}/console/">Pipelines -&gt;</a></p>
	<PanelGroup id={config.panel_groups[0].id} title={config.panel_groups[0].title} panels={config.panel_groups[0].panels.length}>
		<SourceHealthPanel {census} width={console.chart_width} height={console.chart_height}/>
		<FeedsFailedPanel days={windowDays} view={failed ?? (feedsAnswer !== 'pending' ? fallback : null)} {fallback} panelState={feedPanelState} articleState={stateOf(feedsAnswer)}
			width={console.chart_width} height={console.chart_height} tileMinPx={console.tile_min_px} readoutMaxShare={data.chart.readout_max_share} minAttempts={console.min_attempts_for_rate} notes={evidenceOf(feedsAnswer, span)} feedNotes={feedReadNotes(data.feedInput, span)}/>
		<FetchTimePanel days={windowDays} view={times} panelState={stateOf(fetchAnswer)} width={console.chart_width} height={console.chart_height} readoutMaxShare={data.chart.readout_max_share} notes={evidenceOf(fetchAnswer, fetchSpan)}/>
		<RetiringPanel strip={data.retiring} drawing={retirement} cap={console.source_rows} readoutMaxShare={data.chart.readout_max_share} width={console.chart_width} height={console.chart_height}/>
		<SourceCutsPanel days={windowDays} view={cuts} panelState={stateOf(cutsAnswer)} width={console.chart_width} height={console.chart_height} readoutMaxShare={data.chart.readout_max_share} notes={evidenceOf(cutsAnswer, cutsSpan)}/>
	</PanelGroup>
	<PanelGroup id={config.panel_groups[1].id} title={config.panel_groups[1].title} panels={config.panel_groups[1].panels.length}>
		<RankingDiscountPanel {discount} width={console.chart_width} height={console.chart_height}/>
		<WhyChosenPanel view={chosen} panelState={stateOf(chosenAnswer)} width={console.chart_width} height={console.chart_height} readoutMaxShare={data.chart.readout_max_share} notes={evidenceOf(chosenAnswer, chosenSpan)}/>
		<WatchlistPanel days={windowDays} view={catches} panelState={stateOf(watchAnswer)} width={console.chart_width} height={console.chart_height} tileMinPx={console.tile_min_px} readoutMaxShare={data.chart.readout_max_share} notes={evidenceOf(watchAnswer, watchSpan)}/>
	</PanelGroup>
</RouteStatus>
