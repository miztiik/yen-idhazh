<script lang="ts">
	import { base } from '$app/paths';
	import { onMount } from 'svelte';
	import { consoleKnobs, routeConsole } from '$lib/console/route-console';
	import { rangeFor, routeReach, sliceOnce, retryAsks, type PanelQuery, type Range, type RouteReach } from '$lib/console/queries/window';
	import { pipelinesRecord, retryReach } from '$lib/console/pipelines/record-window';
	import * as queries from '$lib/console/queries/pipelines';
	import { settingsRules } from '$lib/console/settings-moved';
	import { daysInWindow, windowOfDays } from '$lib/charts/viewport';
	import { noRecordSentence, setAsideSentence } from '$lib/console/recording';
	import type { LedgerReach, Row, SliceResult } from '$lib/data/ledger';
	import type { PanelState } from '$lib/console/waiting';
	import Panel from '$lib/components/Panel.svelte';
	import PanelGroup from '$lib/components/PanelGroup.svelte';
	import Reserved from '$lib/components/Reserved.svelte';
	import RouteStatus from '$lib/components/RouteStatus.svelte';
	import WindowControlSource from '$lib/components/WindowControlSource.svelte';
	import AtAGlance from '$lib/console/pipelines/AtAGlance.svelte';
	import RunHealth from '$lib/console/pipelines/RunHealth.svelte';
	import SiteCostPerItem from '$lib/console/pipelines/SiteCostPerItem.svelte';
	import FailureMix from '$lib/console/pipelines/FailureMix.svelte';
	import ItemTimeSplit from '$lib/console/pipelines/ItemTimeSplit.svelte';
	import SlowerOnSameWork from '$lib/console/pipelines/SlowerOnSameWork.svelte';
	import StageTimings from '$lib/console/pipelines/StageTimings.svelte';
	import ItemCost from '$lib/console/pipelines/ItemCost.svelte';
	import RunTimeline from '$lib/console/pipelines/RunTimeline.svelte';
	import ChartDrawing from '$lib/console/pipelines/ChartDrawing.svelte';
	import Extraction from '$lib/console/pipelines/Extraction.svelte';
	import ArticleAge from '$lib/console/pipelines/ArticleAge.svelte';

	let { data } = $props();
	const knobs = consoleKnobs();
	const configured = routeConsole('pipelines');
	const asks: readonly PanelQuery[] = [
		queries.failureMixQuery, queries.failedRuleQuery, queries.itemTimeSplitQuery, queries.slowerOnSameWorkQuery,
		queries.stageTimingsQuery, queries.itemCostQuery, queries.runTimelineQuery, queries.extractionQuery,
		queries.extractionScoresQuery, queries.articleAgeQuery
	];
	const readers: Record<string, (range: Range) => Promise<SliceResult>> = {
		[queries.failureMixQuery.name]: (range) => sliceOnce(queries.failureMixQuery, range),
		[queries.failedRuleQuery.name]: (range) => sliceOnce(queries.failedRuleQuery, range),
		[queries.itemTimeSplitQuery.name]: (range) => sliceOnce(queries.itemTimeSplitQuery, range),
		[queries.slowerOnSameWorkQuery.name]: (range) => sliceOnce(queries.slowerOnSameWorkQuery, range),
		[queries.stageTimingsQuery.name]: (range) => sliceOnce(queries.stageTimingsQuery, range),
		[queries.itemCostQuery.name]: (range) => sliceOnce(queries.itemCostQuery, range),
		[queries.runTimelineQuery.name]: (range) => sliceOnce(queries.runTimelineQuery, range),
		[queries.extractionQuery.name]: (range) => sliceOnce(queries.extractionQuery, range),
		[queries.extractionScoresQuery.name]: (range) => sliceOnce(queries.extractionScoresQuery, range),
		[queries.articleAgeQuery.name]: (range) => sliceOnce(queries.articleAgeQuery, range)
	};
	type Answer = SliceResult | LedgerReach | 'pending';
	const WINDOW_KEY = 'idhazh:console-window';
	let windowDays = $state(knobs.default_window_days);
	let mounted = $state(false);
	let reach = $state<RouteReach | null>(null);
	let answers = $state<Record<string, Answer>>(Object.fromEntries(asks.map((query) => [query.name, 'pending'])));
	let ranges = $state<Record<string, Range>>({});
	let revision = 0;
	const allAnswers = $derived(asks.map((query) => answers[query.name]));
	const busy = $derived(allAnswers.some((answer) => answer === 'pending'));
	const recordReady = $derived(mounted && reach?.through !== null && reach?.through !== undefined && !busy);
	const viewport = $derived(windowOfDays(reach?.through ?? data.windowDay, windowDays, knobs.today_anchor));
	const settings = $derived(settingsRules(data, { from: viewport.start, to: viewport.end }, 'none'));
	const charts = $derived(data.charts.filter((day) => day.date >= viewport.start && day.date <= viewport.end));
	const yieldDays = $derived(data.extractionDays.filter((day) => day.date >= viewport.start && day.date <= viewport.end));
	const publishedShare = $derived(data.extractionPublishedByWindow.find((span) => span.days === windowDays && span.through === viewport.end)
		?? { measuredDays: 0, unused: 0, chartablePublished: 0, unusedPct: null });
	const record = $derived(recordReady ? pipelinesRecord(reach, windowDays) : null);

	async function ask(selected: readonly PanelQuery[], retryWindow = false) {
		if (selected.length === 0) return;
		const ticket = ++revision;
		const days = windowDays;
		const previous = retryWindow ? reach : null;
		answers = { ...answers, ...Object.fromEntries(selected.map((query) => [query.name, 'pending'])) };
		ranges = Object.fromEntries(Object.entries(ranges).filter(([name]) => !selected.some((query) => query.name === name)));
		const refreshed = await routeReach(asks.map((query) => query.ledger));
		if (ticket !== revision) return;
		const nextReach = retryWindow ? retryReach(previous, refreshed) : refreshed;
		reach = nextReach;
		await Promise.all(selected.map(async (query) => {
			const range = rangeFor(query, days, nextReach, knobs.window_presets);
			const answer = 'from' in range ? await readers[query.name](range) : range;
			if (ticket === revision) {
				if ('from' in range) ranges = { ...ranges, [query.name]: range };
				answers = { ...answers, [query.name]: answer };
			}
		}));
	}
	onMount(() => {
		mounted = true;
		const stored = Number(preference());
		if (knobs.window_presets.includes(stored)) windowDays = stored;
		void ask(asks);
		return () => { revision += 1; };
	});
	function show(days: number) {
		if (!knobs.window_presets.includes(days)) throw new Error('The window must be a configured preset.');
		windowDays = days;
		preference(String(days));
		void ask(asks);
	}
	function preference(value?: string): string | null {
		try {
			if (value !== undefined) localStorage.setItem(WINDOW_KEY, value);
			return localStorage.getItem(WINDOW_KEY);
		} catch {
			return null;
		}
	}
	function retry() {
		if (busy) return;
		const failed = asks.filter((query) => {
			const answer = answers[query.name];
			return answer !== 'pending' && (answer.state === 'missing' || answer.state === 'unreachable');
		});
		retryAsks(failed);
		void ask(failed, true);
	}
	function rows(query: PanelQuery): Row[] {
		const answer = answers[query.name];
		return answer !== 'pending' && 'rows' in answer ? answer.rows : [];
	}
	function panelState(query: PanelQuery): PanelState {
		const answer = answers[query.name];
		return answer === 'pending' ? 'loading' : answer.state === 'ok' ? 'ready' : answer.state;
	}
	function calendar(query: PanelQuery): string[] {
		const range = ranges[query.name];
		return range === undefined ? [] : daysInWindow({ start: range.from, end: range.to });
	}
	function queryWindow(query: PanelQuery) {
		const range = ranges[query.name];
		return range === undefined ? viewport : { start: range.from, end: range.to };
	}
	function queryRule(query: PanelQuery) {
		const span = queryWindow(query);
		return settingsRules(data, { from: span.start, to: span.end }, 'none');
	}
	const notes = $derived(asks.flatMap((query) => {
		const answer = answers[query.name];
		if (answer === 'pending') return [];
		const lost = 'lostDays' in answer && answer.lostDays.length > 0
			? noRecordSentence(query.ledger, answer.lostDays, () => 'those days are not drawn as zero') : null;
		const aside = 'setAside' in answer ? setAsideSentence(query.ledger, query.ledger, answer.setAside, 'this window') : null;
		const range = ranges[query.name];
		const different = range !== undefined && query.span === 'window' && range.from > viewport.start
			? `${query.name}: recorded from ${range.from} through ${range.to}.` : null;
		return [lost, aside, different].filter((note): note is string => note !== null);
	}));
	const titles: Record<string, string> = {
		'at-a-glance': 'At a glance', 'run-health': 'Run health', 'site-cost-per-item': 'What one more article costs',
		'failure-mix': 'What is failing, by stage', 'item-time-split': "Where an item's time went",
		'slower-on-same-work': 'Whether a run is getting slower on the same work', 'stage-timings': 'Time per item by stage',
		'item-cost': 'What one item cost the model', 'run-timeline': "Where the run's time went, on the run's own clock",
		'chart-drawing': 'Visuals drawn for articles', 'extraction': 'What the extractor found',
		'article-age': 'How old an article was when we published it'
	};
	const panelQueries: Record<string, PanelQuery> = {
		'failure-mix': queries.failureMixQuery, 'item-time-split': queries.itemTimeSplitQuery,
		'slower-on-same-work': queries.slowerOnSameWorkQuery, 'stage-timings': queries.stageTimingsQuery,
		'item-cost': queries.itemCostQuery, extraction: queries.extractionQuery, 'article-age': queries.articleAgeQuery
	};
</script>

<svelte:head><title>Pipelines — Console — {data.ui.site_title}</title><meta name="robots" content="noindex" /></svelte:head>
<WindowControlSource days={windowDays} presets={knobs.window_presets} monthsFor={() => 0}
	ready={mounted} {busy} {record} statusLine={recordReady ? null : 'The record window is not ready.'} onChange={show} />
<RouteStatus route="pipelines" answers={allAnswers} days={windowDays} through={recordReady ? reach?.through : null}
	shimmerAfterMs={knobs.shimmer_after_ms} onRetry={retry}>
	{#each [...new Set(notes)] as note}<p data-record-note>{note}</p>{/each}
	<p class="console-carry" data-console-carry="model">{data.carries.pipelines} <a href="{base}/console/model/">Summaries →</a></p>
	{#each configured.panel_groups as group (group.id)}
		<PanelGroup id={group.id} title={group.title} panels={group.panels.length}>
			{#each group.panels as id (id)}
				{#if id === 'run-health'}
					<RunHealth yieldDays={data.runYieldDays} grid={data.grid} window={viewport} days={windowDays} floorPct={data.floorPct}
						height={knobs.chart_height} width={knobs.chart_width} tickDensity={data.chart.tick_density} readoutMaxShare={data.chart.readout_max_share} />
				{:else}
					<Panel {id} title={titles[id]} wide>
						<div data-windowed={id === 'run-timeline' ? undefined : id} data-window-days={id === 'run-timeline' ? undefined : windowDays}>
						{#if id === 'at-a-glance'}
							<AtAGlance days={data.charts} window={viewport} {knobs} chart={data.chart} />
						{:else if id === 'site-cost-per-item'}
							<SiteCostPerItem manifests={data.manifests} publishedItems={data.publishedItems} window={viewport} {knobs} chart={data.chart} rule={settings} />
						{:else if id === 'chart-drawing'}
							<ChartDrawing days={charts} {windowDays} {knobs} />
						{:else if id === 'run-timeline'}
							<RunTimeline {knobs} chart={data.chart} answer={answers[queries.runTimelineQuery.name]} />
						{:else if id === 'extraction'}
							<Extraction rows={rows(queries.extractionQuery)} nativeState={panelState(queries.extractionQuery)}
								evaluations={panelState(queries.extractionScoresQuery) === 'ready' ? rows(queries.extractionScoresQuery) : null}
								evaluationsState={panelState(queries.extractionScoresQuery)}
								nativeWindow={ranges[queries.extractionQuery.name]} evaluationsWindow={ranges[queries.extractionScoresQuery.name]}
								{knobs} chart={data.chart} rule={settings} {yieldDays} {publishedShare} />
						{:else if id === 'failure-mix'}
							<FailureMix rows={rows(queries.failureMixQuery)} ruleRows={rows(queries.failedRuleQuery)}
								nativeState={panelState(queries.failureMixQuery)} rulesState={panelState(queries.failedRuleQuery)}
								rulesWindow={queryWindow(queries.failedRuleQuery)}
								calendar={calendar(queries.failureMixQuery)} {knobs} chart={data.chart} rule={queryRule(queries.failureMixQuery)} />
						{:else if panelQueries[id] !== undefined}
							{@const query = panelQueries[id]}
							<Reserved record panelState={panelState(query)} height={knobs.chart_height} width={knobs.chart_width} name={id} label={titles[id]}>
								{#if id === 'item-time-split'}
									<ItemTimeSplit rows={rows(query)} calendar={calendar(query)} {knobs} chart={data.chart} rule={queryRule(query)} />
								{:else if id === 'slower-on-same-work'}
									<SlowerOnSameWork rows={rows(query)} calendar={calendar(query)} {knobs} chart={data.chart} rule={queryRule(query)} />
								{:else if id === 'stage-timings'}
									<StageTimings rows={rows(query)} {knobs} chart={data.chart} window={queryWindow(query)} rule={queryRule(query)} />
								{:else if id === 'item-cost'}
									<ItemCost rows={rows(query)} {knobs} chart={data.chart} />
								{:else if id === 'article-age'}
									<ArticleAge rows={rows(query)} {knobs} />
								{/if}
							</Reserved>
						{/if}
						</div>
					</Panel>
				{/if}
			{/each}
		</PanelGroup>
	{/each}
</RouteStatus>
