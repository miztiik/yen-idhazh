<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import { useWindowChoice } from '$lib/console/window-slot';
	import PanelGroup from '$lib/components/PanelGroup.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import WindowControlSource from '$lib/components/WindowControlSource.svelte';
	import WindowCoverage from '$lib/components/WindowCoverage.svelte';
	import RouteStatus from '$lib/components/RouteStatus.svelte';
	import { consoleKnobs, readWriteMetricDefault, routeConsole, routeKnobs, tokenDeviationRules } from '$lib/console/route-console';
	import { routeReach, rangeFor, sliceOnce, retryAsks, tallyAsks, windowRange, type Range, type PanelQuery, type RouteReach } from '$lib/console/queries/window';
	import type { LedgerReach, Row, SliceResult } from '$lib/data/ledger';
	import * as queries from '$lib/console/queries/machine';
	import { tokenDeviationsOnce, type TokenHistory } from '$lib/console/queries/token-deviations';
	import { PANEL_QUERIES, countersFrom, processors, shardCounts, textRows } from '$lib/console/machine/records';
	import { MACHINE_QUERY_GROUPS } from '$lib/console/machine/query-groups';
	import { retryReach } from '$lib/console/pipelines/record-window';
	import { describeRefusedRuns } from '$lib/console/machine/refused-runs';
	import { formatNumber } from '$lib/number-format';
	import { measurementOff, recordingNotes, type RecordRead } from '$lib/console/recording';
	import { settingsRules } from '$lib/console/settings-moved';
	import { machineKeys, machineRamp } from '$lib/charts/machine-colour';
	import { fleetJobs } from '$lib/charts/fleet';
	import { articleCost } from '$lib/console/machine/article-cost';
	import { memoryHeld } from '$lib/console/machine/memory-held';
	import { daysInWindow } from '$lib/charts/viewport';
	import { recordWindowBounds } from '$lib/console/waiting';
	import { rangeBounds, sameBounds } from '$lib/console/window-coverage';
	import RecordFrame from '$lib/console/machine/RecordFrame.svelte';
	import MachineCharts from '$lib/console/machine/MachineCharts.svelte';
	import ContextHeadroomPanel from '$lib/console/machine/ContextHeadroomPanel.svelte';
	import ArticleCostPanel from '$lib/console/machine/ArticleCostPanel.svelte';
	import MemoryHeldPanel from '$lib/console/machine/MemoryHeldPanel.svelte';
	import PlatformMixPanel from '$lib/console/machine/PlatformMixPanel.svelte';
	import PromptReusePanel from '$lib/console/machine/PromptReusePanel.svelte';
	import SlowerOnSameWork from '$lib/console/machine/SlowerOnSameWork.svelte';
	import ReadWritePanel from '$lib/console/machine/ReadWritePanel.svelte';

	let { data } = $props();
	const shared = consoleKnobs();
	const groups = routeConsole('machine').panel_groups;
	const configured = routeKnobs('machine', [
		'slower_machines_min_articles',
		'closest_to_memory_rows', 'context_min_values', 'read_write_default_metric',
		'read_write_history_runs', 'read_write_min_prior_runs', 'read_write_stddev_multiplier'
	]);
	const knobs = { ...configured, fleet_top_kinds: shared.fleet_top_kinds };
	const deviationRules = tokenDeviationRules(knobs);
	const tokenOptions = $derived({
		...deviationRules, settingsFrom: data.settingsMoved?.compared_from ?? null,
		settingsThrough: data.read ? data.band.verdict.date : null,
		changeDays: data.settingsMoved?.changes.map((change) => change.date) ?? []
	});
	const cfg = $derived(data.machineConfig);
	const presets = shared.window_presets;
	const choice = useWindowChoice();
	const windowDays = $derived(choice.days);
	let ready = $state(false);
	let generation = $state(0);
	let reaches = $state.raw<Record<string, RouteReach>>({});
	const reach = $derived(reaches.native ?? null);
	let ranges = $state.raw<Record<string, Range>>({});
	let answers = $state.raw<Record<string, SliceResult | LedgerReach>>({});
	let countFault = $state<string | null>(null);
	let tokenHistory = $state<TokenHistory | null>(null);
	let tokenHistoryRange = $state<Range | null>(null);
	const asked: readonly PanelQuery[] = [
		...MACHINE_QUERY_GROUPS.flatMap((group) => [...group.queries]), queries.servingSpeedQuery
	];
	let requestedDays: number | null = null;
	onMount(() => {
		ready = true;
	});
	function show(days: number) {
		choice.select(days);
	}
	function retry() {
		retryAsks(asked.filter((query) => ['missing', 'unreachable'].includes(answers[query.name]?.state ?? 'loading')));
		generation++;
	}
	function ask(query: PanelQuery, range: Range): Promise<SliceResult> {
		switch (query.name) {
			case 'runShardsQuery': return sliceOnce(queries.runShardsQuery, range);
			case 'slowerMachinesQuery': return sliceOnce(queries.slowerMachinesQuery, range);
			case 'platformMixQuery': return sliceOnce(queries.platformMixQuery, range);
			case 'slowerOnSameWorkQuery': return sliceOnce(queries.slowerOnSameWorkQuery, range);
			case 'closestToMemoryQuery': return sliceOnce(queries.closestToMemoryQuery, range);
			case 'memoryHeldQuery': return sliceOnce(queries.memoryHeldQuery, range);
			case 'contextHeadroomQuery': return sliceOnce(queries.contextHeadroomQuery, range);
			case 'articleCostQuery': return sliceOnce(queries.articleCostQuery, range);
			case 'articleCostHostsQuery': return sliceOnce(queries.articleCostHostsQuery, range);
			case 'promptReuseQuery': return sliceOnce(queries.promptReuseQuery, range);
			case 'readAgainstWrittenQuery': return sliceOnce(queries.readAgainstWrittenQuery, range);
			default: throw new Error(`Hardware has no declared question named ${query.name}.`);
		}
	}
	function monthsFor() { return 0; }
	$effect(() => {
		const days = windowDays;
		const attempt = generation;
		const historyOptions = tokenOptions;
		if (!ready) return;
		let current = true;
		const previous = untrack(() => reaches);
		const retryWindow = requestedDays === days;
		requestedDays = days;
		answers = {};
		reaches = {};
		ranges = {};
		countFault = null;
		tokenHistory = null;
		tokenHistoryRange = null;
		void Promise.all(MACHINE_QUERY_GROUPS.map(async (group) => {
			try {
				const refreshed = await routeReach(group.ledgers);
				if (!current) return;
				const found = retryWindow ? retryReach(previous[group.id] ?? null, refreshed) : refreshed;
				reaches = { ...reaches, [group.id]: found };
				const readHistory = async () => {
					if (group.id !== 'native') return;
					const range = rangeFor({ ...queries.readAgainstWrittenQuery, span: 'widest' }, days, found, presets);
					if ('state' in range) {
						if (current) tokenHistory = { state: range.state, readings: [], incomplete: false };
						return;
					}
					if (current) tokenHistoryRange = range;
					try {
						const result = await tokenDeviationsOnce(range, historyOptions);
						if (current) tokenHistory = result;
					} catch (error) {
						if (!current) return;
						console.warn('[machine] Earlier token history did not arrive.', error);
						tokenHistory = { state: 'unreachable', readings: [], incomplete: false };
					}
				};
				const readServing = async () => {
					if (group.id !== 'native' || found.through === null) return;
					const query = queries.servingSpeedQuery;
					try {
						const serving = await routeReach([query.ledger]);
						// Serving evidence can enrich the widest host window, never shorten it.
						const span = rangeFor(query, days, { ...serving, through: found.through }, presets);
						const result = 'state' in span ? span : await sliceOnce(queries.servingSpeedQuery, span);
						if (current) answers = { ...answers, [query.name]: result };
					} catch (error) {
						if (!current) return;
						console.warn('[machine] The serving record did not arrive.', error);
						answers = { ...answers, [query.name]: { state: 'unreachable' } };
					}
				};
				await Promise.all([readHistory(), readServing(), ...group.queries.map(async (query) => {
					const range = rangeFor(query, days, found, presets);
					let result: SliceResult | LedgerReach = 'state' in range ? range : await ask(query, range);
					if (current && query.name === 'runShardsQuery' && 'rows' in result) {
						try { shardCounts(result.rows); } catch (error) {
							countFault = error instanceof Error ? error.message : 'The count record could not be read.';
							result = { state: 'unreachable' };
						}
					}
					if (current) {
						if ('from' in range) ranges = { ...ranges, [query.name]: range };
						answers = { ...answers, [query.name]: result };
					}
				})]);
			} catch (error) {
				if (!current) return;
				console.warn('[machine] The published record did not arrive.', group.id, error);
				if (group.id === 'native') tokenHistory = { state: 'unreachable', readings: [], incomplete: false };
				answers = { ...answers, ...Object.fromEntries(group.queries.map((query) => [query.name, { state: 'unreachable', fault: 'engine' }])) };
			}
		}));
		return () => { current = false; };
	});
	const through = $derived(reach?.through ?? null);
	const itemReach = $derived(reach?.ledgers['item-health']);
	const record = $derived({
		asked: windowDays, through,
		first: through !== null && itemReach?.state === 'ok' && itemReach.first <= through ? itemReach.first : null
	});
	const packedWindow = $derived(recordWindowBounds(record));
	const range = $derived(through === null ? null : windowRange(windowDays, through, '0001-01-01'));
	const start = $derived(range?.from ?? '');
	const end = $derived(range?.to ?? '');
	function rows(name: string): Row[] {
		const answer = answers[name];
		return answer !== undefined && 'rows' in answer ? answer.rows : [];
	}
	function panelState(id: string) { return tallyAsks(PANEL_QUERIES[id].map((query) => answers[query.name] ?? 'pending')).state; }
	const panelAnswers = $derived(groups.flatMap((group) => group.panels.map((id) => {
		const state = panelState(id); return state === 'loading' ? 'pending' as const : { state } as LedgerReach;
	})));
	const routeAnswers = $derived([...panelAnswers, answers.runShardsQuery ?? 'pending']);
	function complete(names: string[]) { return names.every((name) => ['ok', 'quiet'].includes(answers[name]?.state ?? 'loading')); }
	const counterReady = $derived(complete(['platformMixQuery', 'articleCostQuery', 'runShardsQuery']));
	const counters = $derived(countersFrom(counterReady ? rows('platformMixQuery') : [], counterReady ? rows('articleCostQuery') : [], counterReady ? rows('runShardsQuery') : []));
	const countedRuns = $derived(counters.runs.filter((run) => run.date >= start && run.date <= end).length);
	const refused = $derived(describeRefusedRuns(counters.refused.filter((run) => run.date >= start && run.date <= end)));
	const jobs = $derived(fleetJobs(rows('platformMixQuery'), rows(queries.servingSpeedQuery.name)));
	const keys = $derived(machineKeys(jobs.map((job) => ({
		fingerprint: job.fingerprint, fingerprintVersion: job.fingerprintVersion, cpuModel: job.cpuModel
	}))));
	const ramp = $derived(machineRamp(jobs.map((job) => ({
		machine: keys({ fingerprint: job.fingerprint, fingerprintVersion: job.fingerprintVersion, cpuModel: job.cpuModel }), rate: job.rate
	})), { stops: shared.machine_colour_stops, floor: shared.machine_colour_floor_share }));
	const healthDates = $derived([...new Set(rows('closestToMemoryQuery').map((row) => String(row.date)))]);
	const hostDates = $derived(new Set(rows('platformMixQuery').map((row) => String(row.date))));
	const firstHostDate = $derived([...hostDates].sort()[0] ?? null);
	const explicitlyLost = $derived('lostDays' in (answers.platformMixQuery ?? {}) ? (answers.platformMixQuery as Extract<SliceResult, { state: 'ok' }>).lostDays : []);
	const lost = $derived((complete(['closestToMemoryQuery', 'platformMixQuery']) ? healthDates : []).filter((date) =>
		!hostDates.has(date) && ((firstHostDate !== null && date >= firstHostDate) || explicitlyLost.includes(date))).map((date) => ({
		date, articles: new Set(rows('closestToMemoryQuery').filter((row) => row.date === date).map((row) => row.item_id)).size
	})).filter((day) => day.articles > 0));
	function recordRead(name: string, ledger: 'host-fingerprint' | 'item-health'): RecordRead {
		const answer = answers[name], held = reach?.ledgers[ledger];
		if (held?.state === 'missing') return { state: 'not-packed' };
		if (held?.state !== 'ok' || answer === undefined || !('lostDays' in answer)) return { state: 'unreadable', at: null, fault: null };
		return { state: 'read', first: held.first, through: held.through, lastRows: held.lastRows, lostDays: answer.lostDays, setAside: answer.setAside };
	}
	const open = $derived({ start, end, days: windowDays });
	const hostRead = $derived(recordRead('platformMixQuery', 'host-fingerprint'));
	const recordNotes = $derived(recordingNotes({ enabled: cfg.recording, recorded: [...hostDates],
		window: healthDates, reads: [hostRead], from: through === null ? '' : windowRange(Math.max(...presets), through, '0001-01-01').from,
		open, lost, figures: 'machine record' }));
	const off = $derived(measurementOff({ enabled: cfg.recording, recorded: [...hostDates], read: hostRead, open,
		offered: through === null ? [] : presets.map((days) => { const one = windowRange(days, through, '0001-01-01'); return { start: one.from, end: one.to, days }; }) }));
	const serverNotes = $derived(recordingNotes({ enabled: cfg.recording,
		recorded: [...new Set(jobs.filter((job) => job.rate !== null).map((job) => job.date))],
		window: healthDates, reads: [hostRead], from: through === null ? '' : windowRange(Math.max(...presets), through, '0001-01-01').from,
		open, figures: 'server figures', coveredElsewhere: healthDates, missing: 'server-counters' }));
	const lostSentence = $derived(lost.length ? `${lost.reduce((n, day) => n + day.articles, 0)} dated article records have no machine record on ${lost.map((day) => day.date).join(', ')}. The article work was recorded; no machine measurement can be inferred.` : null);
	const recordingGaps = $derived(Boolean((ready && off) || recordNotes.startedMidWindow ||
		serverNotes.startedMidWindow || serverNotes.coveredElsewhere || lostSentence));
	const evidence = $derived(recordingGaps || countFault !== null || refused !== null);
	const sameWorkRange = $derived(ranges[queries.slowerOnSameWorkQuery.name]);
	const promptRange = $derived(ranges[queries.promptReuseQuery.name]);
	const contextRange = $derived(ranges[queries.contextHeadroomQuery.name]);
	const sameWorkCalendar = $derived(sameWorkRange === undefined ? [] : daysInWindow({ start: sameWorkRange.from, end: sameWorkRange.to }));
	const sameWorkRule = $derived(settingsRules(data, { from: sameWorkRange?.from ?? '', to: sameWorkRange?.to ?? '' }, 'none'));
	function panelCoverage(id: string) {
		if (id === 'memory-held') return []; // The panel names the run it actually draws.
		const windows = PANEL_QUERIES[id].flatMap((query) => {
			const span = rangeBounds(ranges[query.name]);
			const state = answers[query.name]?.state;
			return span !== null && (state === 'ok' || state === 'quiet') ? [{ span, source: query.ledger }] : [];
		});
		return windows.filter(({ span }, index) => !windows.slice(0, index).some((other) => sameBounds(span, other.span)));
	}
	const titles: Readonly<Record<string, string>> = {
		'slower-machines': 'Time for the same work by CPU', 'platform-mix': 'Which machines ran our jobs, day by day',
		'slower-on-same-work': 'Whether a run is getting slower on the same work',
		'closest-to-memory': 'Articles with the least memory left', 'memory-held': "What is holding the machine's memory",
		'context-headroom': 'Summary prompt use and room left', 'article-cost': 'What one article costs the machine',
		'prompt-reuse': 'How much of each prompt was already cached', 'read-against-written': 'What a run reads against what it writes'
	};
</script>

<svelte:head><title>Hardware &mdash; Console &mdash; {data.ui.site_title}</title><meta name="robots" content="noindex" /></svelte:head>
<RouteStatus route="machine" answers={routeAnswers} days={windowDays} {through} shimmerAfterMs={shared.shimmer_after_ms} onRetry={retry}
	settledSuffix={counterReady ? `${formatNumber(countedRuns, cfg.chart.number_format, { exact: true })} ${countedRuns === 1 ? 'run' : 'runs'} counted.` : ''}>
<div data-machine-start={start} data-machine-end={end} data-machine-run-count={counterReady ? countedRuns : undefined}>
	<WindowControlSource route="machine" days={windowDays} {presets} {monthsFor} {ready} onChange={show}
		busy={panelAnswers.includes('pending')}
		{record} />
	{#if evidence}
	<details class="machine-evidence" data-machine-evidence>
		<summary>
			{#if recordingGaps}{ready && off ? 'Measurement is off' : 'Recording gaps'}{refused || countFault ? '; ' : '.'}{/if}
			{#if refused}{formatNumber(refused.runs.length, cfg.chart.number_format, { exact: true })} {refused.runs.length === 1 ? 'run excluded' : 'runs excluded'} from run count. {refused.runs.length === 1 ? 'Its' : 'Their'} articles still count.{/if}
			{#if countFault} Run count unavailable.{/if}
		</summary>
		<div class="machine-evidence-body">
	{#if countFault}<p data-machine-count-refusal>{countFault} No planned count can be used until this record is corrected.</p>{/if}
	{#if ready && off}<p data-recording="machine-off">{off}</p>{/if}
	{#if recordNotes.startedMidWindow}<p data-recording="machine-started">{recordNotes.startedMidWindow}</p>{/if}
	{#if serverNotes.startedMidWindow}<p data-recording="server-started">{serverNotes.startedMidWindow}</p>{/if}
	{#if serverNotes.coveredElsewhere}<p data-recording="server-elsewhere">{serverNotes.coveredElsewhere}</p>{/if}
	{#if lostSentence}<p data-recording="machine-destroyed">{lostSentence}</p>{/if}
	{#if refused}
		<div data-machine-refused={refused.runs.length}><p>{refused.head}</p>
			{#each refused.runs as run (run.runId)}<p data-refused-run={run.runId}>{run.runId}: {run.says}</p>{/each}
		</div>
	{/if}
		</div>
	</details>
	{/if}
	{#each groups as group (group.id)}
		<PanelGroup id={group.id} title={group.title} panels={group.panels.length}>
			{#each group.panels as id (id)}
				<RecordFrame {id} title={titles[id]} state={panelState(id)} height={cfg.chart.height_px} width={cfg.chart.width_px} {retry}
					windowed={id === 'slower-on-same-work' ? { name: id, days: windowDays } : undefined}>
					{#snippet coverage()}
						{@const spans = panelCoverage(id)}
						{#each spans as entry (entry.source)}
							<WindowCoverage span={entry.span} common={packedWindow} source={spans.length > 1 ? entry.source : undefined} />
						{/each}
					{/snippet}
					{#if id === 'platform-mix'}
						<PlatformMixPanel {ramp} {start} {end} {windowDays} {lost} {jobs} recording={cfg.recording}
							chart={cfg.chart} knobs={shared} />
					{:else if id === 'article-cost'}
						<ArticleCostPanel cost={articleCost(textRows(rows('articleCostQuery')), processors(rows('articleCostHostsQuery')))}
							days={windowDays} {windowDays} chart={cfg.chart} />
					{:else if id === 'memory-held'}
						<MemoryHeldPanel record={memoryHeld(textRows(rows('memoryHeldQuery')), cfg.chart.number_format)} start={end} {end} days={1} />
					{:else if id === 'context-headroom'}
						{#if contextRange !== undefined}
							<ContextHeadroomPanel rows={rows(queries.contextHeadroomQuery.name)} title={titles[id]} range={contextRange}
								chart={cfg.chart} minValues={knobs.context_min_values} {windowDays} />
						{/if}
					{:else if id === 'read-against-written'}
						<ReadWritePanel rows={rows('readAgainstWrittenQuery')} chart={cfg.chart} shell={data}
							initialMetric={readWriteMetricDefault(knobs.read_write_default_metric)}
							history={tokenHistory} historyRange={tokenHistoryRange} {deviationRules}
							{start} {end} {windowDays} />
					{:else if id === 'prompt-reuse'}
						{#if promptRange !== undefined}
							<PromptReusePanel rows={rows('promptReuseQuery')} title={titles[id]} chart={cfg.chart} shell={data}
								range={promptRange} {windowDays} />
						{/if}
					{:else if id === 'slower-on-same-work'}
						<Panel {id} title={titles[id]} heading="h3">
							<div>
								<SlowerOnSameWork rows={rows(queries.slowerOnSameWorkQuery.name)} calendar={sameWorkCalendar}
									knobs={shared} chart={cfg.chart} rule={sameWorkRule} />
							</div>
						</Panel>
					{:else}
						<MachineCharts {id} title={titles[id]} rows={rows(PANEL_QUERIES[id][0].name)}
							hostRows={id === 'slower-machines' ? rows('platformMixQuery') : []}
							chart={cfg.chart} {knobs} />
					{/if}
				</RecordFrame>
			{/each}
		</PanelGroup>
	{/each}
</div>
</RouteStatus>

<style>
	.machine-evidence {
		margin-block: var(--console-control-gap);
		border: 1px solid var(--color-rule);
		border-radius: var(--console-control-radius);
		font-size: var(--console-small-size);
		line-height: var(--console-small-leading);
	}
	summary {
		min-block-size: var(--console-control-min-height);
		padding: var(--console-control-padding-block) var(--console-control-padding-inline);
		align-content: center;
		color: var(--color-accent);
		cursor: pointer;
	}
	.machine-evidence-body { display: grid; gap: var(--console-control-padding-block); padding: var(--console-panel-padding); border-block-start: 1px solid var(--color-rule); }
	.machine-evidence-body p { margin: 0; }
</style>
