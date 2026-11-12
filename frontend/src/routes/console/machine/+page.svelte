<script lang="ts">
	import { onMount } from 'svelte';
	import { useWindowChoice } from '$lib/console/window-slot';
	import PanelGroup from '$lib/components/PanelGroup.svelte';
	import WindowControlSource from '$lib/components/WindowControlSource.svelte';
	import RouteStatus from '$lib/components/RouteStatus.svelte';
	import { consoleKnobs, readWriteMetricDefault, routeConsole, routeKnobs } from '$lib/console/route-console';
	import { routeReach, rangeFor, sliceOnce, retryAsks, tallyAsks, windowRange, type Range, type PanelQuery, type RouteReach } from '$lib/console/queries/window';
	import type { LedgerReach, Row, SliceResult } from '$lib/data/ledger';
	import * as queries from '$lib/console/queries/machine';
	import { compareRuns } from '$lib/console/queries/shared';
	import { PANEL_QUERIES, countersFrom, processors, shardCounts, textRows } from '$lib/console/machine/records';
	import { describeRefusedRuns } from '$lib/console/machine/refused-runs';
	import { finiteCell } from '$lib/console/rates';
	import { formatNumber } from '$lib/number-format';
	import { measurementOff, recordingNotes, type RecordRead } from '$lib/console/recording';
	import { settingsRules } from '$lib/console/settings-moved';
	import { machineKeys, machineRamp } from '$lib/charts/machine-colour';
	import { fleetJobs } from '$lib/charts/fleet';
	import { articleCost } from '$lib/console/machine/article-cost';
	import { memoryHeld } from '$lib/console/machine/memory-held';
	import { percentileHistory } from '$lib/charts/machine';
	import RecordFrame from '$lib/console/machine/RecordFrame.svelte';
	import MachineCharts from '$lib/console/machine/MachineCharts.svelte';
	import ArticleCostPanel from '$lib/console/machine/ArticleCostPanel.svelte';
	import MemoryHeldPanel from '$lib/console/machine/MemoryHeldPanel.svelte';
	import PlatformMixPanel from '$lib/console/machine/PlatformMixPanel.svelte';
	import TailTrendPanel from '$lib/console/machine/TailTrendPanel.svelte';
	import ReadWritePanel from '$lib/console/machine/ReadWritePanel.svelte';

	let { data } = $props();
	const shared = consoleKnobs();
	const groups = routeConsole('machine').panel_groups;
	const configured = routeKnobs('machine', [
		'clocks_agree_within_pct', 'slower_machines_min_articles',
		'closest_to_memory_rows', 'context_min_values', 'read_write_default_metric'
	]);
	const knobs = { ...configured, fleet_top_kinds: shared.fleet_top_kinds };
	const cfg = $derived(data.machineConfig);
	const presets = shared.window_presets;
	const choice = useWindowChoice();
	const windowDays = $derived(choice.days);
	let ready = $state(false);
	let generation = $state(0);
	let reach = $state<RouteReach | null>(null);
	let answers = $state<Record<string, SliceResult | LedgerReach>>({});
	let countFault = $state<string | null>(null);
	const asked = [...new Map([...Object.values(PANEL_QUERIES).flat(), queries.platformMixQuery, queries.articleCostQuery]
		.map((query) => [query.name, query])).values()];
	onMount(() => {
		ready = true;
	});
	function show(days: number) {
		choice.select(days);
	}
	function retry() {
		retryAsks(asked.filter((query) => answers[query.name]?.state === 'unreachable'));
		generation++;
	}
	function ask(query: PanelQuery, range: Range): Promise<SliceResult> {
		switch (query.name) {
			case 'runShardsQuery': return sliceOnce(queries.runShardsQuery, range);
			case 'twoClocksQuery': return sliceOnce(queries.twoClocksQuery, range);
			case 'twoClocksHostsQuery': return sliceOnce(queries.twoClocksHostsQuery, range);
			case 'slowerMachinesQuery': return sliceOnce(queries.slowerMachinesQuery, range);
			case 'platformMixQuery': return sliceOnce(queries.platformMixQuery, range);
			case 'tailTrendQuery': return sliceOnce(queries.tailTrendQuery, range);
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
		if (!ready) return;
		let current = true;
		answers = {};
		reach = null;
		countFault = null;
		void (async () => {
			try {
				const found = await routeReach(['item-health', 'host-fingerprint', 'run-shards']);
				if (!current) return;
				reach = found;
				await Promise.all(asked.map(async (query) => {
					const range = rangeFor(query, days, found, presets);
					let result: SliceResult | LedgerReach = 'state' in range ? range : await ask(query, range);
					if (current && query.name === 'runShardsQuery' && 'rows' in result) {
						try { shardCounts(result.rows); } catch (error) {
							countFault = error instanceof Error ? error.message : 'The count record could not be read.';
							result = { state: 'unreachable' };
						}
					}
					if (current) answers = { ...answers, [query.name]: result };
				}));
			} catch (error) {
				if (!current) return;
				console.warn('[machine] The published record did not arrive.', error);
				answers = Object.fromEntries(asked.map((query) => [query.name, { state: 'unreachable', fault: 'engine' }]));
			}
		})();
		return () => { current = false; };
	});
	const through = $derived(reach?.through ?? null);
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
	function complete(names: string[]) { return names.every((name) => ['ok', 'quiet'].includes(answers[name]?.state ?? 'loading')); }
	const counterReady = $derived(complete(['platformMixQuery', 'articleCostQuery', 'runShardsQuery']));
	const counters = $derived(countersFrom(counterReady ? rows('platformMixQuery') : [], counterReady ? rows('articleCostQuery') : [], counterReady ? rows('runShardsQuery') : [],
		{ contextWindow: cfg.contextWindow, jobTimeoutSeconds: cfg.jobTimeoutSeconds }));
	const countedRuns = $derived(counters.runs.filter((run) => run.date >= start && run.date <= end).length);
	const latestRunId = $derived([...new Set([...rows('platformMixQuery').filter((row) => row.date === end),
		...rows('twoClocksQuery')].map((row) => String(row.run_id)))].sort(compareRuns).at(-1) ?? null);
	const newest = $derived(counters.runs.find((run) => run.runId === latestRunId) ?? null);
	const clockReady = $derived(complete(['platformMixQuery', 'twoClocksQuery', 'runShardsQuery']));
	const clockCounters = $derived(countersFrom(clockReady ? rows('platformMixQuery').filter((row) => row.date === end) : [],
		rows('twoClocksQuery'), rows('runShardsQuery'), { contextWindow: cfg.contextWindow, jobTimeoutSeconds: cfg.jobTimeoutSeconds }));
	const refused = $derived(describeRefusedRuns(counters.refused.filter((run) => run.date >= start && run.date <= end)));
	const jobs = $derived(fleetJobs(rows('platformMixQuery')));
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
		recorded: [...new Set(rows('platformMixQuery').filter((row) => finiteCell(row.server_prompt_tokens) !== null &&
			finiteCell(row.server_prompt_seconds) !== null).map((row) => String(row.date)))],
		window: healthDates, reads: [hostRead], from: through === null ? '' : windowRange(Math.max(...presets), through, '0001-01-01').from,
		open, figures: 'server figures', coveredElsewhere: healthDates, missing: 'server-counters' }));
	const lostSentence = $derived(lost.length ? `${lost.reduce((n, day) => n + day.articles, 0)} dated article records have no machine record on ${lost.map((day) => day.date).join(', ')}. The article work was recorded; no machine measurement can be inferred.` : null);
	const recordingGaps = $derived(Boolean((ready && off) || recordNotes.startedMidWindow ||
		serverNotes.startedMidWindow || serverNotes.coveredElsewhere || lostSentence));
	const evidence = $derived(recordingGaps || countFault !== null || refused !== null);
	const latency = $derived(percentileHistory(textRows(rows('tailTrendQuery')), shared.min_attempts_for_rate));
	const settings = $derived(settingsRules(data, { from: start, to: end }, 'none'));
	const changes = $derived('changes' in settings ? settings.changes : []);
	const changeNote = $derived('note' in settings ? settings.note : settings.declined);
	const titles: Readonly<Record<string, string>> = {
		'two-clocks': 'Clock agreement',
		'slower-machines': 'Which machines do the same work slower', 'platform-mix': 'Which machines ran our jobs, day by day',
		'tail-trend': 'Whether the slowest articles are getting slower',
		'closest-to-memory': 'Which articles left the machine least memory', 'memory-held': "What is holding the machine's memory",
		'context-headroom': 'How much of the reading limit an article takes', 'article-cost': 'What one article costs the machine',
		'prompt-reuse': 'How much text the model reads again', 'read-against-written': 'What a run reads against what it writes'
	};
</script>

<svelte:head><title>Hardware &mdash; Console &mdash; {data.ui.site_title}</title><meta name="robots" content="noindex" /></svelte:head>
<RouteStatus route="machine" answers={panelAnswers} days={windowDays} {through} shimmerAfterMs={shared.shimmer_after_ms} onRetry={retry}
	settledSuffix={counterReady ? `${formatNumber(countedRuns, cfg.chart.number_format, { exact: true })} ${countedRuns === 1 ? 'run' : 'runs'} counted.` : ''}>
<div data-machine-start={start} data-machine-end={end} data-machine-run-count={counterReady ? countedRuns : undefined}>
	<WindowControlSource route="machine" days={windowDays} {presets} {monthsFor} {ready} onChange={show}
		busy={panelAnswers.includes('pending')}
		record={{ asked: windowDays, first: reach?.ledgers['item-health']?.state === 'ok' ? reach.ledgers['item-health'].first : null, through }} />
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
				<RecordFrame {id} title={titles[id]} state={panelState(id)} height={cfg.chart.height_px} width={cfg.chart.width_px} {retry}>
					{#if id === 'platform-mix'}
						<PlatformMixPanel {ramp} {start} {end} {windowDays} {lost} recordRows={rows('platformMixQuery')} recording={cfg.recording}
							gradients={cfg.gradients} chart={cfg.chart} knobs={shared} />
					{:else if id === 'article-cost'}
						<ArticleCostPanel cost={articleCost(textRows(rows('articleCostQuery')), processors(rows('articleCostHostsQuery')))}
							days={windowDays} {windowDays} chart={cfg.chart} />
					{:else if id === 'memory-held'}
						<MemoryHeldPanel record={memoryHeld(textRows(rows('memoryHeldQuery')), cfg.chart.number_format)} start={end} {end} days={1} />
					{:else if id === 'read-against-written'}
						<ReadWritePanel rows={rows('readAgainstWrittenQuery')} chart={cfg.chart} shell={data}
							initialMetric={readWriteMetricDefault(knobs.read_write_default_metric)}
							{start} {end} {windowDays} />
					{:else if id === 'tail-trend'}
						<TailTrendPanel rows={latency.runs} {start} {end} modelChanges={changes.map((move) => move.date)}
							missingMarkers={changeNote} moved={changes.map((move) => ({ date: move.date, settings: [move.words] }))}
							chart={cfg.chart} {windowDays} days={windowDays} floor={latency.floor} tooFew={latency.tooFew} />
					{:else}
						<MachineCharts {id} newestRunId={latestRunId} title={titles[id]} rows={id === 'two-clocks'
							? rows('twoClocksQuery').filter((row) => row.machine_job === null || row.machine_job === '' || row.machine_job === 'work')
							: rows(PANEL_QUERIES[id][0].name)}
							newest={id === 'two-clocks' ? clockCounters.runs.find((run) => run.runId === latestRunId) ?? null : newest}
							chart={cfg.chart} shell={data} {start} {end} {knobs} {windowDays} />
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
