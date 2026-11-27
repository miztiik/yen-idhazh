<script lang="ts">
	/** Draw one judge's reported cohorts and inspect the work behind each date. */
	import ChartReadout from '$lib/components/ChartReadout.svelte';
	import { daySlots } from '$lib/charts/day-slots';
	import { chartWidth, observeWidth } from '$lib/charts/frame';
	import { useChartLabels } from '$lib/charts/label-context';
	import { columnPick, pointerReadout, readoutMarks, readoutOf } from '$lib/charts/readout';
	import { axisLabels, slotCellFor } from '$lib/charts/run-history';
	import { councilOutcomeLabel, councilPartCounts, type CouncilWork } from '$lib/console/council-runs';
	import { longDate } from '$lib/format';

	let { judge, days, calendar, width, density, maxShare }: {
		judge: string; days: ReadonlyMap<string, readonly CouncilWork[]>; calendar: readonly string[];
		width: number; density: number; maxShare: number;
	} = $props();
	const labels = useChartLabels();
	let measured = $state<number | null>(null);
	let pointed = $state<string | null>(null);
	let picked = $state<string | null>(null);
	const newest = $derived(calendar.findLast((day) => days.has(day)) ?? calendar.at(-1) ?? '');
	const chosen = $derived(picked !== null && calendar.includes(picked) ? picked : newest);
	const hoverAt = $derived(pointed === null ? -1 : calendar.indexOf(pointed));
	const at = $derived(hoverAt === -1 ? calendar.indexOf(chosen) : hoverAt);
	const selected = $derived(days.get(chosen) ?? []);
	const plotSlots = $derived(daySlots(chartWidth(measured, width), calendar.length, { left: 0, right: 0 }));
	const ticks = $derived(axisLabels([...calendar], { density, pitch: plotSlots.slot, labels: labels() }));
	const marks = $derived(readoutMarks(plotSlots.centres));
	const fits = $derived(slotCellFor(plotSlots.slot) !== null);
	const maxParts = $derived([...days.values()].reduce((max, work) =>
		work.reduce((largest, one) => Math.max(largest, one.expected ?? 0,
			one.parts.size + Number(one.expected === null)), max), 1));
	const readout = $derived(readoutOf({
		type: 'dateSeries', columns: calendar.map((date) => `${longDate(date)} UTC`),
		series: [{
			label: 'Reported work', swatch: null, values: calendar.map((date) => days.get(date)?.length ?? null), format: String
		}],
		events: { lines: calendar.map((date) => (days.get(date) ?? []).map((one) => ({
			label: longDate(one.digest),
			value: one.noWork ? 'No work assigned' : `${one.parts.size} parts reported` +
				`${one.expected === null ? '; total unknown' : ` of ${one.expected} expected`}; combine: ${councilOutcomeLabel(one.combine)}`,
			swatch: null
		}))), none: 'No recorded work' },
		notMeasured: 'No recorded work', resting: 'last'
	}));

	function shape(work: CouncilWork) {
		const counts = councilPartCounts(work);
		const order = ['completed', 'nothing_to_do', 'stopped_on_deadline', 'failed', 'unreported'] as const;
		const segments: { state: (typeof order)[number] | 'unknown'; share: number; count: number }[] = order
			.filter((state) => counts[state] > 0).map((state) => ({
				state, share: counts[state] / maxParts * 100, count: counts[state]
			}));
		if (work.expected === null) segments.push({ state: 'unknown', share: 100 / maxParts, count: 1 });
		return segments;
	}

	function combine(work: CouncilWork): string {
		if (work.combine !== null) return work.combine;
		return work.noWork ? 'nothing_to_do' : 'unreported';
	}

	function pick(index: number) { picked = calendar[index] ?? null; }
</script>

<section class="judge-chart" aria-label={`Work reported by ${judge}`}>
	<h3>{judge.replaceAll('-', ' ')}</h3>
	<div class="grid-layout" class:fits>
		<div class="labels" aria-hidden="true"><span>Combine</span><span>Parts</span></div>
		<div class="plot" use:observeWidth={(next) => measured = next}>
			{#if fits}
					<!-- svelte-ignore a11y_no_noninteractive_tabindex (One stop for the date readout.) -->
					<div role="group" tabindex="0" class="marks" aria-label={`${judge}: parts and combine by UTC execution day`}
						data-chart-type="dateSeries" data-chart-name={`council-${judge}`} data-readout-columns={calendar.length}
						style:--dates={calendar.length}
						use:pointerReadout={{ marks, width: plotSlots.width, selected: at,
							onSelect: (column) => pointed = column === null ? null : calendar[column] ?? null,
							hover: { name: `council-${judge}`, readout } }}
						use:columnPick={{ marks, width: plotSlots.width, showing: at, onPick: pick }}>
						{#each calendar as date (date)}
							<div class="date" class:chosen={calendar[at] === date} aria-hidden="true">
								{#each days.get(date) ?? [] as work (work.key)}
									<div class="cohort">
										<span class="combine" data-outcome={combine(work)}></span>
										<div class="parts">
											{#each shape(work) as segment (segment.state)}
												<span data-outcome={segment.state} style:block-size={`${segment.share}%`}
													style:--parts={segment.count}></span>
											{/each}
										</div>
									</div>
								{/each}
							</div>
						{/each}
					</div>
					<div class="axis" style:--dates={calendar.length} aria-hidden="true">
						{#each ticks as tick (tick.column)}
							<span class={tick.align} style:grid-column={tick.column}>{tick.text}</span>
						{/each}
					</div>
			{:else}
				<label class="compact-days">Inspect UTC execution day
					<input type="range" min="0" max={calendar.length - 1} step="1" value={calendar.indexOf(chosen)}
						aria-valuetext={longDate(chosen)} oninput={(event) => pick(event.currentTarget.valueAsNumber)} />
				</label>
			{/if}
		</div>
	</div>
	<p class="key"><span><i data-outcome="completed"></i> Completed</span>
		<span><i data-outcome="unreported"></i> Not reported</span>
		<span><i data-outcome="nothing_to_do"></i> No work</span>
		<span><i data-outcome="stopped_on_deadline"></i> Deadline</span>
		<span><i data-outcome="failed"></i> Failed</span></p>
	<ChartReadout {readout} {at} name={`council-${judge}`} {maxShare}
		hint={fits ? 'Use Left and Right to read a day. Press Enter to inspect its work.' : ''} />
	{#if selected.length}
		<details>
			<summary>Judged digests on {longDate(chosen)} UTC</summary>
			<ul>
				{#each selected as work (work.key)}
					{@const counts = councilPartCounts(work)}
					<li>
						<strong>{longDate(work.digest)} UTC</strong> / Attempt {work.attempt.attempt}
						{#if work.noWork}/ No work assigned
						{:else}/ {counts.reported} parts reported{work.expected === null ? '; total unknown' : ` of ${work.expected} expected`}
							/ {counts.completed} completed
							{#if counts.stopped_on_deadline} / {counts.stopped_on_deadline} stopped at deadline{/if}
							{#if counts.failed} / {counts.failed} failed{/if}
							/ Combine: {councilOutcomeLabel(work.combine)}
						{/if}
					</li>
				{/each}
			</ul>
		</details>
	{/if}
</section>

<style>
	.judge-chart { border-block-start: 1px solid var(--color-rule); padding-block: var(--space-2); }
	h3 { margin: 0 0 var(--space-2); font-size: var(--console-body-size); overflow-wrap: anywhere; }
	.grid-layout { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: var(--space-2); }
	.labels { display: grid; grid-template-rows: var(--space-3) var(--space-8); align-items: center; color: var(--color-text-secondary); font-size: var(--console-small-size); }
	.grid-layout:not(.fits) .labels { visibility: hidden; block-size: 0; overflow: hidden; }
	.marks, .axis { display: grid; grid-template-columns: repeat(var(--dates), minmax(0, 1fr)); }
	.marks { border-block-end: 1px solid var(--color-rule); }
	.marks:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
	.date { display: flex; justify-content: center; gap: 1px; padding-inline: 1px; min-inline-size: 0; }
	.date.chosen { background: var(--color-surface-sunken); }
	.cohort { display: grid; grid-template-rows: var(--space-3) var(--space-8); align-items: center; flex: 1 1 0; max-inline-size: var(--space-5); min-inline-size: 0; }
	.combine { block-size: var(--console-chart-line-width); inline-size: 100%; }
	.combine[data-outcome='unreported'] { background: none; }
	.parts { block-size: 100%; display: flex; flex-direction: column-reverse; }
	.parts span { position: relative; }
	.parts span::after {
		content: ''; position: absolute; inset: 0; background-image:
			linear-gradient(to top, var(--color-surface) 1px, transparent 1px);
		background-size: 100% calc(100% / var(--parts));
	}
	[data-outcome='completed'] { background: var(--operation-written); }
	[data-outcome='stopped_on_deadline'] { background: var(--operation-deferred); }
	[data-outcome='failed'] { background: var(--operation-failed); }
	.parts [data-outcome='stopped_on_deadline'], .key [data-outcome='stopped_on_deadline'] {
		background-image: repeating-linear-gradient(90deg, transparent 0 2px, var(--color-surface) 2px 3px);
	}
	.parts [data-outcome='failed'], .key [data-outcome='failed'] {
		background-image: repeating-linear-gradient(45deg, transparent 0 3px, var(--color-surface) 3px 4px);
	}
	[data-outcome='nothing_to_do'] { border: 1px solid var(--color-rule-strong); }
	[data-outcome='unreported'], [data-outcome='unknown'] { background: repeating-linear-gradient(135deg, transparent 0 2px, var(--color-rule-strong) 2px 3px); }
	.axis, .key, details, .compact-days { color: var(--color-text-secondary); font-size: var(--console-small-size); }
	.axis span { white-space: nowrap; justify-self: center; }
	.axis .start { justify-self: start; }
	.axis .end { justify-self: end; }
	.key { display: flex; flex-wrap: wrap; gap: var(--space-1) var(--space-3); margin-block: var(--space-1); }
	.key span { display: inline-flex; align-items: center; gap: var(--space-1); }
	.key i { inline-size: var(--space-3); block-size: var(--space-3); }
	.compact-days { display: grid; gap: var(--space-1); }
	.compact-days input { accent-color: var(--color-accent); }
	summary { cursor: pointer; }
	ul { margin-block: var(--space-1); padding-inline-start: var(--space-4); }
</style>
