<script lang="ts">
	/** Put the latest verified monthly write above the three grains of compact evidence. */
	import Panel from '$lib/components/Panel.svelte';
	import DateTileGrid from '$lib/charts/d3/DateTileGrid.svelte';
	import { COMPACT_PERIODS, type Period } from '$lib/data/compact-index';
	import type { CompactPeriodReading, CompactWriteRequest, CompactWriteTrack } from '$lib/data/compact-file-writes';
	import type { CompactWrite } from '$lib/data/compact-write-footer';
	import { compactLedgerNames, compactPeriod, compactWrites } from '$lib/data/ledger';
	import { readSession } from '$lib/data/read-session';
	import { longDate } from '$lib/format';
	import type { ChartConfig, ConsoleConfig } from '$lib/server/config';
	import { compactActivity, PERIOD_LABEL, periodLabel, utcTime, writeInstant } from './gardener-activity';
	import GardenerTaskReports from './GardenerTaskReports.svelte';

	let { days, knobs, chart, limits }: {
		days: number; knobs: ConsoleConfig; chart: ChartConfig; limits: Pick<CompactWriteRequest, 'maxFiles' | 'maxBytes'>
	} = $props();
	const id = 'gardener-activity';
	const ledgers = compactLedgerNames();
	const widest = $derived(Math.max(...knobs.window_presets));
	let tracks = $state.raw<Partial<Record<Period, CompactWriteTrack>>>({});
	let retryCount = $state(0);
	let picked = $state('');
	let ledger = $state('');
	let period = $state<Period>('monthly');
	let covers = $state<string | null>(null);
	let detailOpen = $state(false);
	let detail = $state.raw<{ key: string; answer: CompactPeriodReading | 'pending' } | null>(null);

	const view = $derived(compactActivity(tracks, days));
	const monthly = $derived(tracks.monthly);
	const lead = $derived(view.monthly);
	const monthlyShared = $derived(monthly?.spans.find(({ from, to }) => monthly?.spans.every((span) => span.from === from && span.to === to)));
	const chosen = $derived(view.calendar.includes(picked) ? picked : view.calendar.at(-1) ?? '');
	const writes = $derived(view.byDay.get(chosen) ?? []);
	const target = $derived({
		ledger: ledger || lead?.ledger || ledgers[0] || '',
		period,
		covers: covers ?? (period === 'monthly' ? lead?.covers ?? '' : '')
	});
	const keyFor = (value: typeof target) => JSON.stringify([value.ledger, value.period, value.covers]);
	const shown = $derived(detail === null || detail.key !== keyFor(target) ? null : detail.answer);
	const keyOf = (write: CompactWrite) => JSON.stringify([write.ledger, write.period, write.covers]);

	$effect(() => {
		const request = { ...limits, days, presets: knobs.window_presets };
		void retryCount;
		const session = readSession();
		let active = true;
		tracks = {};
		const answers = compactWrites(request);
		for (const period of COMPACT_PERIODS) {
			void answers[period].then((answer) => {
				if (active && session === readSession()) tracks = { ...tracks, [period]: answer };
			}, (error: unknown) => {
				if (!active || session !== readSession()) return;
				console.warn(`[gardener] ${period} compact evidence did not arrive.`, error);
				tracks = { ...tracks, [period]: { period, candidates: 0, writes: [], issues: ['The compact record did not arrive.'],
					spans: [], days: request.days, omitted: false } };
			});
		}
		return () => { active = false; };
	});

	async function readPeriod() {
		const request = target;
		const key = keyFor(request);
		const session = readSession();
		const waiting = { key, answer: 'pending' } as const;
		detail = waiting;
		try {
			const answer = await compactPeriod(request.ledger, request.period, request.covers, limits);
			if (detail === waiting && session === readSession()) detail = { key, answer };
		} catch (error) {
			if (detail !== waiting || session !== readSession()) return;
			console.warn('[gardener] The selected period could not be read.', error);
			detail = { key, answer: { state: 'unavailable' } };
		}
	}

	function inspectWrite(key: string) {
		const write = writes.find((item) => keyOf(item) === key);
		if (!write) return;
		ledger = write.ledger;
		period = write.period;
		covers = write.covers;
		detailOpen = true;
		void readPeriod();
	}
</script>

<Panel {id} title="Gardener maintenance" heading="h3" wide>
	<div class="maintenance" data-panel-question="When did Gardener write compact files?"
		data-model-rule-name={id} data-model-rule="no" data-model-rule-none="The record shows dated maintenance writes, not model settings.">
		<noscript><p>JavaScript is needed to read the published Gardener records.</p></noscript>
		<div class="monthly">
			<h4>Latest recorded monthly compaction</h4>
			{#if lead}
				<p class="lead" data-lede><time datetime={writeInstant(lead)}>{utcTime(writeInstant(lead))}</time></p>
				<p>Covered month: <strong>{periodLabel('monthly', lead.covers)}</strong>.</p>
				<p class="note">Published month-file write. {view.monthlyGroup.length} of {monthly?.writes.length} verified month files
					belong to this wake and month.{monthly?.issues.length ? ' Some evidence is unavailable.' : ''}</p>
			{:else if monthly === undefined}
				<p class="note" role="status">Checking published month files.</p>
			{:else if monthly.omitted}
				<p class="note">Monthly files not checked: the available set exceeds the read limit.</p>
			{:else if monthly.issues.length}
				<p class="note">Monthly write evidence did not arrive in full. No write date could be verified.</p>
			{:else}
				<p class="note">No dated monthly write in the available publication.</p>
			{/if}
			{#if monthlyShared}
				<p class="note">Published evidence for periods covering {longDate(monthlyShared.from)} to {longDate(monthlyShared.to)} UTC.</p>
			{:else if monthly && monthly.spans.length}
				<p class="note">Published evidence within up to {widest} covered days per ledger; see evidence scope below.</p>
			{/if}
		</div>

		<div class="activity">
			<h4>Compaction activity</h4>
			{#if view.calendar.length}
				<p class="note">UTC write days. Filled: published write. Outline: none found in checked files. Dashed: evidence incomplete.</p>
				<DateTileGrid days={view.calendar} lanes={view.lanes} name="gardener-writes" label="Published compact writes by UTC day"
					chosen={view.calendar.indexOf(chosen)}
					onPick={(at) => { if (view.calendar[at]) picked = view.calendar[at]; }} width={knobs.chart_width}
					density={chart.tick_density} maxShare={chart.readout_max_share} />
				<div class="controls">
					<label>Write day (UTC)
						<select class="control" value={chosen} onchange={(event) => picked = event.currentTarget.value}>
							{#each [...view.calendar].reverse() as date (date)}<option value={date}>{longDate(date)}</option>{/each}
						</select>
					</label>
					{#if writes.length > 0}
						<label>Inspect a write
							<select class="control" value="" onchange={(event) => inspectWrite(event.currentTarget.value)}>
								<option value="" disabled>Choose a ledger and period</option>
								{#each writes as write (keyOf(write))}
									<option value={keyOf(write)}>{PERIOD_LABEL[write.period]}: {periodLabel(write.period, write.covers)} - {write.ledger}</option>
								{/each}
							</select>
						</label>
					{/if}
				</div>
			{:else}
				<p class="note" role="status">{COMPACT_PERIODS.some((grain) => tracks[grain] === undefined)
					? 'Checking published compact files.' : 'No dated writes found in the checked publication.'}</p>
			{/if}
			{#each COMPACT_PERIODS as grain (grain)}
				{@const track = tracks[grain]}
				{#if track?.omitted}<p class="note">{PERIOD_LABEL[grain]}: not checked; indexed files exceed the read limit.</p>
				{:else if track?.issues.length}<p class="note">{PERIOD_LABEL[grain]}: evidence incomplete.</p>
				{:else if track?.candidates === 0}<p class="note">{PERIOD_LABEL[grain]}: no published files named in the checked range.</p>{/if}
				{#if grain === 'daily' && track && !track.omitted && track.days < days}
					<p class="note">Daily: checked up to {track.days} covered days per ledger instead of {days} to stay within the file and byte limits.</p>
				{/if}
			{/each}
			{#if COMPACT_PERIODS.some((grain) => tracks[grain]?.issues.length)}
				<button type="button" class="control" onclick={() => retryCount += 1}>Retry write evidence</button>
			{/if}
		</div>

		<GardenerTaskReports {days} presets={knobs.window_presets} />
		<details bind:open={detailOpen}>
			<summary>Compaction details</summary>
			<form class="controls" onsubmit={(event) => { event.preventDefault(); void readPeriod(); }}>
				<label>Ledger
					<select class="control" value={target.ledger} onchange={(event) => ledger = event.currentTarget.value}>
						{#each ledgers as name (name)}<option value={name}>{name}</option>{/each}
					</select>
				</label>
				<label>Grain
					<select class="control" value={period} onchange={(event) => {
						const next = COMPACT_PERIODS.find((grain) => grain === event.currentTarget.value);
						if (next) { period = next; covers = ''; }
					}}>
						{#each COMPACT_PERIODS as grain (grain)}<option value={grain}>{PERIOD_LABEL[grain]}</option>{/each}
					</select>
				</label>
				<label>Covered period (UTC)
					<input class="control" type="text" value={target.covers} required
						pattern={period === 'yearly' ? '[0-9]{4}' : period === 'monthly' ? '[0-9]{4}-[0-9]{2}' : '[0-9]{4}-[0-9]{2}-[0-9]{2}'}
						placeholder={period === 'yearly' ? 'YYYY' : period === 'monthly' ? 'YYYY-MM' : 'YYYY-MM-DD'}
						oninput={(event) => covers = event.currentTarget.value} />
				</label>
				<button class="control" type="submit" disabled={!target.ledger || shown === 'pending'}>Read period</button>
			</form>
			{#if shown === 'pending'}<p class="note" role="status">Checking this period.</p>
			{:else if shown?.state === 'coverage' || shown?.state === 'packed'}
				{@const { entry, write } = shown}
				<p>{periodLabel(target.period, entry.covers)}: {entry.state === 'lost' ? 'Record lost.' : entry.state === 'empty'
					? 'Checked, no file was written.' : `Published compact file (${entry.rows} rows).`}</p>
				{#if write}
					<p class="note">Written <time datetime={writeInstant(write)}>{utcTime(writeInstant(write))}</time>.
						Run {write.runId}, attempt {write.attempt}, shard {write.shard}.</p>
				{:else if shown.state === 'packed'}<p class="note">Write time and wake could not be verified.</p>{/if}
				{#if entry.lost_days?.length}<p class="note">Lost dates: {entry.lost_days.map(longDate).join(', ')} UTC.</p>{/if}
				{#if entry.set_aside}<p class="note">{entry.set_aside} input files set aside unread.</p>{/if}
			{:else if shown?.state === 'coarser'}
				<p>Covered by a {PERIOD_LABEL[shown.period].toLowerCase()} file for {periodLabel(shown.period, shown.covers)}. No separate write date is known for the requested period.</p>
			{:else if shown?.state === 'expired'}
				<p>Expired through {shown.through} UTC. The index supplies no removal time or count.</p>
			{:else if shown?.state === 'unavailable'}<p>Evidence unavailable for this period.</p>
			{:else if shown?.state === 'unrecorded'}<p>No published file or coverage found for this period.</p>{/if}
		</details>
		<details>
			<summary>Evidence scope</summary>
			<p class="note">Only retained, indexed files within the published window can establish a write. A missing write does not establish that the workflow did not run.</p>
			{#each COMPACT_PERIODS as grain (grain)}
				{@const track = tracks[grain]}
				{#if track}
					<h4>{PERIOD_LABEL[grain]}</h4>
					<ul>
						{#each track.spans as span (span.ledger)}
							<li>{span.ledger}: {longDate(span.from)} to {longDate(span.to)} UTC covered days.</li>
						{/each}
						{#each track.issues as issue}<li>{issue}</li>{/each}
					</ul>
				{/if}
			{/each}
		</details>
	</div>
</Panel>

<style>
	.maintenance { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--space-2); overflow-wrap: anywhere; }
	.activity { border-block-start: 1px solid var(--color-rule); padding-block-start: var(--space-3); }
	.lead { font: var(--console-panel-title-weight) var(--console-panel-title-size)/var(--console-panel-title-leading) var(--font-display); font-variant-numeric: tabular-nums; }
	h4, p { margin-block: 0 var(--space-1); }
	.note { color: var(--color-text-secondary); font-size: var(--console-small-size); }
	.controls { display: flex; flex-wrap: wrap; align-items: end; gap: var(--space-2) var(--space-4); margin-block: var(--space-2); }
	label { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--space-1); min-inline-size: 0; max-inline-size: 100%; }
	.control { max-inline-size: 100%; min-block-size: var(--console-control-min-height); color: inherit; background: var(--color-surface); border: 1px solid var(--color-rule-strong); border-radius: var(--console-control-radius); padding-inline: var(--console-control-padding-inline); font: inherit; }
	summary { cursor: pointer; min-block-size: var(--console-control-min-height); }
	ul { margin-block: var(--space-1) var(--space-3); padding-inline-start: var(--space-4); }
</style>
