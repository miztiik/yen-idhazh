<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import { useWindowChoice } from '$lib/console/window-slot';
	import { consoleKnobs, routeConsole, routeKnobs } from '$lib/console/route-console';
	import { rangeFor, routeReach, sliceOnce, retryAsks, type PanelQuery, type Range, type RouteReach } from '$lib/console/queries/window';
	import { pipelinesRecord, retryReach } from '$lib/console/pipelines/record-window';
	import { PIPELINES_QUERY_GROUPS } from '$lib/console/pipelines/query-groups';
	import * as queries from '$lib/console/queries/pipelines';
	import { settingsRules } from '$lib/console/settings-moved';
	import { daysInWindow, windowOfDays } from '$lib/charts/viewport';
	import { countDays } from '$lib/console/span-words';
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
	import TimeCost from '$lib/console/TimeCost.svelte';
	import RunTimeline from '$lib/console/pipelines/RunTimeline.svelte';
	import SlowestArticles from '$lib/console/pipelines/SlowestArticles.svelte';
	import ChartDrawing from '$lib/console/pipelines/ChartDrawing.svelte';
	import ArticleAge from '$lib/console/pipelines/ArticleAge.svelte';
	import VisualRefusals from '$lib/console/pipelines/VisualRefusals.svelte';

	let { data } = $props();
	const knobs = consoleKnobs();
	const configured = routeConsole('pipelines');
	const ranking = routeKnobs('machine', ['slowest_articles_rows']);
	const asks: readonly PanelQuery[] = PIPELINES_QUERY_GROUPS.flatMap((group) => [...group.queries]);
	const readers: Record<string, (range: Range) => Promise<SliceResult>> = {
		[queries.failureMixQuery.name]: (range) => sliceOnce(queries.failureMixQuery, range),
		[queries.failedRuleQuery.name]: (range) => sliceOnce(queries.failedRuleQuery, range),
		[queries.itemTimeSplitQuery.name]: (range) => sliceOnce(queries.itemTimeSplitQuery, range),
		[queries.slowerOnSameWorkQuery.name]: (range) => sliceOnce(queries.slowerOnSameWorkQuery, range),
		[queries.stageTimingsQuery.name]: (range) => sliceOnce(queries.stageTimingsQuery, range),
		[queries.writeCostQuery.name]: (range) => sliceOnce(queries.writeCostQuery, range),
		[queries.runTimelineQuery.name]: (range) => sliceOnce(queries.runTimelineQuery, range),
		[queries.slowestArticlesQuery.name]: (range) => sliceOnce(queries.slowestArticlesQuery, range),
		[queries.articleAgeQuery.name]: (range) => sliceOnce(queries.articleAgeQuery, range)
	};
	type Answer = SliceResult | LedgerReach | 'pending';
	const choice = useWindowChoice();
	const windowDays = $derived(choice.days);
	let mounted = $state(false);
	let reaches = $state<Record<string, RouteReach>>({});
	const reach = $derived(reaches.native ?? null);
	let answers = $state<Record<string, Answer>>(Object.fromEntries(asks.map((query) => [query.name, 'pending'])));
	let ranges = $state<Record<string, Range>>({});
	let revision = 0;
	const allAnswers = $derived(asks.map((query) => answers[query.name]));
	const busy = $derived(allAnswers.some((answer) => answer === 'pending'));
	const nativeBusy = $derived(PIPELINES_QUERY_GROUPS[0].queries.some((query) => answers[query.name] === 'pending'));
	const recordReady = $derived(mounted && reach?.through !== null && reach?.through !== undefined && !nativeBusy);
	const viewport = $derived(windowOfDays(data.windowDay, windowDays, knobs.today_anchor));
	const settings = $derived(settingsRules(data, { from: viewport.start, to: viewport.end }, 'none'));
	const charts = $derived(data.charts.filter((day) => day.date >= viewport.start && day.date <= viewport.end));
	const attemptDays = $derived(data.visualAttempts.days.filter((day) => day.date >= viewport.start && day.date <= viewport.end));
	const record = $derived(recordReady ? pipelinesRecord(reach, windowDays) : null);

	async function ask(selected: readonly PanelQuery[], retryWindow = false, days = windowDays) {
		if (selected.length === 0) return;
		const ticket = ++revision;
		answers = { ...answers, ...Object.fromEntries(selected.map((query) => [query.name, 'pending'])) };
		ranges = Object.fromEntries(Object.entries(ranges).filter(([name]) => !selected.some((query) => query.name === name)));
		async function read(query: PanelQuery, nextReach: RouteReach) {
			const range = rangeFor(query, days, nextReach, knobs.window_presets);
			const answer = 'from' in range ? await readers[query.name](range) : range;
			if (ticket === revision) {
				if ('from' in range) ranges = { ...ranges, [query.name]: range };
				answers = { ...answers, [query.name]: answer };
			}
		}
		await Promise.all(PIPELINES_QUERY_GROUPS.map(async (group) => {
			const names = new Set<string>(group.queries.map((query) => query.name));
			const chosen = selected.filter((query) => names.has(query.name));
			if (chosen.length === 0) return;
			const previous = retryWindow ? reaches[group.id] ?? null : null;
			const refreshed = await routeReach(group.ledgers);
			if (ticket !== revision) return;
			const nextReach = retryWindow ? retryReach(previous, refreshed) : refreshed;
			reaches = { ...reaches, [group.id]: nextReach };
			await Promise.all(chosen.map((query) => read(query, nextReach)));
		}));
	}
	onMount(() => {
		mounted = true;
		return () => { revision += 1; };
	});
	$effect(() => {
		const days = windowDays;
		if (mounted) untrack(() => { void ask(asks, false, days); });
	});
	function show(days: number) {
		choice.select(days);
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
		return [lost, aside].filter((note): note is string => note !== null);
	}));
	const titles: Record<string, string> = {
		'at-a-glance': 'At a glance', 'run-health': 'Run health', 'site-cost-per-item': 'What one more article costs',
		'failure-mix': 'What is failing, by stage', 'item-time-split': "Where an item's time went",
		'slower-on-same-work': 'Whether a run is getting slower on the same work', 'stage-timings': 'Time per item by stage',
		'write-cost': 'What one summary cost', 'run-timeline': "Where the run's time went, on the run's own clock",
		'slowest-articles': 'Which articles took longest in the last run',
		'chart-drawing': 'Visuals drawn for articles',
		'visual-refusals': 'Recorded refusal reasons over time',
		'article-age': 'Source age at work start'
	};
	const panelQueries: Record<string, PanelQuery> = {
		'failure-mix': queries.failureMixQuery, 'item-time-split': queries.itemTimeSplitQuery,
		'slower-on-same-work': queries.slowerOnSameWorkQuery, 'stage-timings': queries.stageTimingsQuery,
		'write-cost': queries.writeCostQuery, 'article-age': queries.articleAgeQuery,
		'slowest-articles': queries.slowestArticlesQuery
	};
</script>

<svelte:head><title>Pipelines — Console — {data.ui.site_title}</title><meta name="robots" content="noindex" /></svelte:head>
<noscript><p data-native-script-required>The article record needs JavaScript to load. Private published-day panels remain available below.</p></noscript>
<WindowControlSource route="pipelines" days={windowDays} presets={knobs.window_presets} monthsFor={() => 0}
	ready={mounted} {busy} {record} publishedWindow={viewport} statusLine={recordReady ? null : 'The record window is not ready.'} onChange={show} />
<RouteStatus route="pipelines" answers={allAnswers} days={windowDays} through={recordReady ? reach?.through : null}
	recordScope="Native record"
	shimmerAfterMs={knobs.shimmer_after_ms} onRetry={retry}>
	{#each configured.panel_groups as group (group.id)}
		<PanelGroup id={group.id} title={group.title} panels={group.panels.length}>
			{#each group.panels as id (id)}
				{#if id === 'run-health'}
					<RunHealth yieldDays={data.runYieldDays} grid={data.grid} window={viewport} days={windowDays} floorPct={data.floorPct}
						height={knobs.chart_height} width={knobs.chart_width} tickDensity={data.chart.tick_density} readoutMaxShare={data.chart.readout_max_share} />
				{:else}
					<Panel {id} title={titles[id]} wide={['at-a-glance', 'run-timeline', 'chart-drawing', 'visual-refusals'].includes(id)} verdict={id === 'at-a-glance'}>
						<div data-windowed={['run-timeline', 'slowest-articles', 'chart-drawing'].includes(id) ? undefined : id} data-window-days={['run-timeline', 'slowest-articles', 'chart-drawing'].includes(id) ? undefined : windowDays}
							data-window-exempt={id === 'slowest-articles' ? 'newest-run' : undefined}
							aria-label={['run-timeline', 'slowest-articles', 'chart-drawing'].includes(id) ? undefined : `${titles[id]}, selected window ${countDays(windowDays)}`}
							data-readout-fetched={panelQueries[id] !== undefined || id === 'run-timeline' ? '' : undefined}>
						{#if id === 'at-a-glance'}
							<AtAGlance days={data.charts} publishedItems={data.publishedItems} window={viewport} {knobs} chart={data.chart} />
						{:else if id === 'site-cost-per-item'}
							<SiteCostPerItem manifests={data.manifests} publishedItems={data.publishedItems} window={viewport} {knobs} chart={data.chart} rule={settings} />
						{:else if id === 'chart-drawing'}
							<ChartDrawing days={charts} {windowDays} {knobs} />
						{:else if id === 'visual-refusals'}
							<VisualRefusals days={attemptDays} read={data.visualAttempts.read} window={viewport} {knobs} chart={data.chart} />
						{:else if id === 'run-timeline'}
							<RunTimeline {knobs} chart={data.chart} answer={answers[queries.runTimelineQuery.name]} />
						{:else if id === 'failure-mix'}
							<FailureMix rows={rows(queries.failureMixQuery)} ruleRows={rows(queries.failedRuleQuery)}
								nativeState={panelState(queries.failureMixQuery)} rulesState={panelState(queries.failedRuleQuery)}
								rulesWindow={queryWindow(queries.failedRuleQuery)}
								calendar={calendar(queries.failureMixQuery)} {knobs} chart={data.chart} rule={queryRule(queries.failureMixQuery)} />
							{#each [...new Set(notes)] as note}<p data-record-note>{note}</p>{/each}
						{:else if panelQueries[id] !== undefined}
							{@const query = panelQueries[id]}
							<Reserved record panelState={panelState(query)} height={knobs.chart_height} width={knobs.chart_width} name={id} label={titles[id]}>
								{#if id === 'item-time-split'}
									<ItemTimeSplit rows={rows(query)} calendar={calendar(query)} {knobs} chart={data.chart} rule={queryRule(query)} />
								{:else if id === 'slower-on-same-work'}
									<SlowerOnSameWork rows={rows(query)} calendar={calendar(query)} {knobs} chart={data.chart} rule={queryRule(query)} />
								{:else if id === 'stage-timings'}
									<StageTimings rows={rows(query)} {knobs} chart={data.chart} window={queryWindow(query)} rule={queryRule(query)} />
								{:else if id === 'write-cost'}
									<TimeCost id="write-cost" rows={rows(query)} range={ranges[query.name]} chart={data.chart} />
								{:else if id === 'article-age'}
									<ArticleAge rows={rows(query)} {knobs} />
								{:else if id === 'slowest-articles'}
									<SlowestArticles rows={rows(query)} chart={data.chart} limit={ranking.slowest_articles_rows} />
								{/if}
							</Reserved>
						{/if}
						{#if panelQueries[id] !== undefined && ranges[panelQueries[id].name] !== undefined}
							{@const range = ranges[panelQueries[id].name]}
							<p data-native-window data-range-from={range.from} data-range-to={range.to}>Native record: {range.from} through {range.to} UTC.</p>
						{/if}
						</div>
					</Panel>
				{/if}
			{/each}
		</PanelGroup>
	{/each}
</RouteStatus>
