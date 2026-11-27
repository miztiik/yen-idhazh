<script lang="ts">
	/** Show retained pack writes and task outcomes under one UTC calendar. */
	import DateTileGrid from '$lib/charts/d3/DateTileGrid.svelte';
	import type { TimeWindow } from '$lib/charts/viewport';
	import Panel from '$lib/components/Panel.svelte';
	import Reserved from '$lib/components/Reserved.svelte';
	import { COMPACT_PERIODS } from '$lib/data/compact-index';
	import type { ChartConfig, ConsoleConfig } from '$lib/server/config';
	import { longDate } from '$lib/format';
	import { compactActivity, PERIOD_LABEL, periodLabel, utcTime, writeInstant } from './gardener-activity';
	import type { OperationReading, PackTracks } from './operation-reads.svelte';
	import GardenerTaskReports from './GardenerTaskReports.svelte';

	let { viewport, days, knobs, chart, tracks, reading, busy, onRetryPacks }: {
		viewport: TimeWindow; days: number; knobs: ConsoleConfig;
		chart: Pick<ChartConfig, 'tick_density' | 'readout_max_share'>;
		tracks: PackTracks; reading: OperationReading; busy: boolean; onRetryPacks: () => void;
	} = $props();
	let picked = $state<string | null>(null);
	const view = $derived(compactActivity(tracks, viewport, days));
	const chosen = $derived(picked !== null && view.calendar.includes(picked) ? picked : viewport.end);
	const selected = $derived(view.byDay.get(chosen) ?? []);
	const latest = $derived(selected[0] ?? (picked === null || picked !== chosen ? view.latest : null));
	const limited = $derived(tracks.daily !== undefined && !tracks.daily.omitted && tracks.daily.days < days);
	const errors = $derived(COMPACT_PERIODS.flatMap((period) => tracks[period]?.issues ?? []));
	const pending = $derived(reading.answer === 'pending' && COMPACT_PERIODS.every((period) => tracks[period] === undefined));
</script>

<Panel id="gardener-activity" title="Gardener" wide>
	<div class="maintenance" data-panel-question="When were the indexed packs written?"
		data-model-rule-name="gardener-activity" data-model-rule="no"
		data-model-rule-none="The record shows dated maintenance writes, not model settings.">
		<Reserved panelState={pending ? 'loading' : 'ready'} height={knobs.chart_height} width={knobs.chart_width}
			name="gardener-writes" label="Gardener writes and reported task outcomes">
		<div class="lead">
			{#if view.monthly}
				<p class="milestone" data-monthly-write>
					<span class="written" aria-hidden="true"></span>
					<strong>Latest monthly write:</strong> <time datetime={writeInstant(view.monthly)}>{utcTime(writeInstant(view.monthly))}</time>
					<span>{view.monthlyGroup.length} {view.monthlyGroup.length === 1 ? 'pack' : 'packs'} for {periodLabel('monthly', view.monthly.covers)}</span>
				</p>
			{/if}
			{#if latest}
				<dl class="receipt" data-pack-receipt>
					<dt>{latest.ledger} <time datetime={writeInstant(latest)}>{utcTime(writeInstant(latest))}</time></dt>
					<dd>Covers {periodLabel(latest.period, latest.covers)}</dd>
					<dd>{latest.rows.toLocaleString('en')} rows
						{#if latest.inputs !== null} / {latest.inputs.toLocaleString('en')} input files{/if}
						/ {latest.bytes.toLocaleString('en')} bytes</dd>
				</dl>
			{/if}
		</div>
		<GardenerTaskReports calendar={view.calendar} day={chosen} {reading}>
			{#snippet plot(outcomes)}
				<DateTileGrid days={view.calendar} lanes={[...view.lanes, ...outcomes]} name="gardener-writes"
					label="Gardener writes and reported task outcomes by UTC day" chosen={view.calendar.indexOf(chosen)}
					onPick={(at) => { picked = view.calendar[at] ?? null; }} width={knobs.chart_width}
					density={chart.tick_density} maxShare={chart.readout_max_share} />
			{/snippet}
		</GardenerTaskReports>
		<p class="note">
			<span class="legend"><i data-key="write"></i> Pack written</span>
			<span class="legend"><i data-key="failed"></i> Failed</span>
			<span class="legend"><i data-key="deferred"></i> Deferred or limited</span>
			<span class="legend"><i data-key="recovered"></i> Recovery</span>
		</p>
		<details>
			<summary>What the write marks mean</summary>
			<p>A green check confirms a Gardener write timestamp in a retained pack, not a successful workflow run.</p>
			<p>Hatched means the check was incomplete; outlined means no write was found in the packs checked. Older daily packs can be merged or expire.</p>
			{#if limited}<p>The read limit allowed up to {tracks.daily?.days} covered days per ledger for this {days}-day window.</p>{/if}
		</details>
		{#if selected.length > 1}
			<details>
				<summary>Pack receipts for {longDate(chosen)} UTC</summary>
				<ul>
					{#each selected as pack (`${pack.ledger}/${pack.period}/${pack.covers}`)}
						<li>{pack.ledger} / {PERIOD_LABEL[pack.period]} / Covers {periodLabel(pack.period, pack.covers)}
							/ <time datetime={writeInstant(pack)}>{utcTime(writeInstant(pack))}</time>
							/ {pack.rows.toLocaleString('en')} rows
							{#if pack.inputs !== null} / {pack.inputs.toLocaleString('en')} input files{/if}
							/ {pack.bytes.toLocaleString('en')} bytes</li>
					{/each}
				</ul>
			</details>
		{/if}
		{#if errors.length || COMPACT_PERIODS.some((period) => tracks[period]?.omitted)}
			<details>
				<summary>Incomplete pack evidence</summary>
				<ul>
					{#each COMPACT_PERIODS.filter((period) => tracks[period]?.omitted) as period (period)}
						<li>{PERIOD_LABEL[period]} files exceed the read limit.</li>
					{/each}
					{#each errors as error (error)}<li>{error}</li>{/each}
				</ul>
				{#if errors.length}<button type="button" disabled={busy} onclick={onRetryPacks}>Retry pack check</button>{/if}
			</details>
		{/if}
		</Reserved>
	</div>
</Panel>

<style>
	.maintenance { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--space-2); overflow-wrap: anywhere; }
	.lead { display: flex; align-items: start; justify-content: space-between; flex-wrap: wrap; gap: var(--space-3); }
	p, dd, dl { margin: 0; }
	.note, .receipt, details { color: var(--color-text-secondary); font-size: var(--console-small-size); }
	.milestone { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-2); margin-block-start: var(--space-2); }
	.written { inline-size: var(--space-3); block-size: var(--space-3); background: var(--operation-written); }
	.legend { display: inline-flex; gap: var(--space-1); align-items: center; margin-inline-end: var(--space-3); }
	.legend i { inline-size: var(--space-2); block-size: var(--space-2); background: var(--operation-written); }
	.legend [data-key='failed'] { background: var(--operation-failed); }
	.legend [data-key='deferred'] { background: var(--operation-deferred); block-size: var(--console-chart-line-width); }
	.legend [data-key='recovered'] { background: var(--chart-1); scale: .7; rotate: 45deg; }
	.receipt { background: var(--color-surface-raised); border: 1px solid var(--color-rule); border-radius: var(--console-control-radius); padding: var(--space-2) var(--space-3); }
	dt { font-weight: 600; color: var(--color-text); }
	summary { cursor: pointer; }
	button { text-decoration: underline; }
	ul { margin-block: var(--space-1); padding-inline-start: var(--space-4); }
</style>
