<script lang="ts">
	import type { Retiring } from '../../server/source-retiring';
	import type { retirementDrawing } from './retiring';
	import TargetBar from '../../components/TargetBar.svelte';
	import ChartReadout from '../../components/ChartReadout.svelte';
	import { markReadout } from '../../charts/readout';
	import VoicesPanel from './VoicesPanel.svelte';
	import RecordFrame from './RecordFrame.svelte';
	let { strip, drawing, cap, readoutMaxShare, width, height }: {
		strip: Retiring | null; drawing: ReturnType<typeof retirementDrawing>; cap: number; readoutMaxShare: number; width: number; height: number;
	} = $props();
	let selected = $state<number | null>(null);
</script>
<VoicesPanel id="retiring" title="Sources close to retiring themselves" question="what happened"
	comparison="distance against the retirement rule" reason="distance from the run's retirement rule, not a model trend">
	{#if strip === null}
		<div data-retiring="absent"><RecordFrame panelState="missing" {width} {height} name="retiring" label="Sources close to retiring" kind="rankedList">{#snippet children()}{/snippet}</RecordFrame></div>
	{:else if strip.rows.length + strip.hidden + strip.unjudged.length + strip.unjudgedHidden + strip.clear === 0}
		<div data-retiring-empty><RecordFrame panelState="quiet" {width} {height} name="retiring" label="Sources close to retiring" kind="rankedList">{#snippet children()}{/snippet}</RecordFrame></div>
	{:else}
		<p data-lede>{strip.rows.length + strip.hidden} sources are close to retiring themselves.</p>
		<p class="notes" data-retiring-lead data-window-exempt="retiring">Run {strip.runId} counted this distance. A source under {Math.round(strip.alarmPoint * 100)}% every day for {strip.dwellDays} days running stops being asked. This does not follow the window control.</p>
		{#if !strip.autoRetire}<p class="notes" data-retiring-watching>Nothing retires on this measurement yet — this panel is watching only.</p>{/if}
		<p class="notes" data-retiring-clear>{strip.clear} judged sources are at or above the mark today.</p>
		<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
		<div class="evidence" data-chart-type="rankedList" data-chart-name="source-yield" data-retiring="table" data-retiring-dwell={strip.dwellDays} data-retiring-auto={strip.autoRetire ? 'yes' : 'no'}
			data-retiring-drawn={strip.rows.length} data-retiring-hidden={strip.hidden} data-retiring-cap={cap}
			data-readout-records={drawing.records.length || undefined} data-readout-none={drawing.records.length ? undefined : 'no source has a day on record, so there is no square to read; agreed with Susan'}
			tabindex={drawing.records.length ? 0 : undefined} role="group" aria-label={strip.dates.length === 1
				? "Every source's reading for the one recorded day, one square per source. Arrow keys move between sources. Escape returns to the first source."
				: "Every source's days, one square a day. Arrow keys read a square, Escape returns to the first source's newest day."}
			use:markReadout={{ count: drawing.records.length, walk: Math.max(1, strip.dates.length), selected, onSelect: (index) => selected = index }}>
			{#if strip.rows.length === 0 && strip.unjudged.length === 0}
				<p class="notes" data-retiring-empty>{#if strip.clear > 0}No source is close to retiring itself.{:else}The census arrived successfully, but no source has a yield to judge. This is not a missing census.{/if}</p>
			{/if}
			<ol class="source-rows" data-retiring-rows>
				{#each strip.rows as row (row.sourceId)}
					<li data-retiring-row={row.sourceId} data-retiring-days-under={row.daysUnder} data-retiring-on={row.retiresOn} data-retiring-track={row.marks.track}>
						<p>{row.title} <small data-source-note-id>{row.sourceId}</small> {#if row.retired}<span data-retiring-chip>retired</span>{:else if row.daysLeft !== null}<span data-retiring-chip>retires in {row.daysLeft} {row.daysLeft === 1 ? 'day' : 'days'}</span>{/if}</p>
						<div data-retiring-cell="bar"><TargetBar marks={row.marks} label="Published out of offered" valueText={row.share === null ? 'no decisions' : `${Math.round(row.share * 100)}%`} targetText="retires under {Math.round(strip.alarmPoint * 100)}%" emptyNote="This source has decided nothing yet." tone="health"/></div>
						{#if row.squares.length}
							<div class="squares" data-retiring-strip={row.sourceId} style="grid-template-columns: repeat({strip.dates.length}, {drawing.cell.cell}px); gap: {drawing.cell.gap}px">
								{#each row.squares as square (square.date)}
									{@const at = drawing.index.get(`${row.sourceId}|${square.date}`)}
									<span class="square" style="block-size: {drawing.cell.cell}px" data-readout-at={at} data-readout-picked={selected === at ? 'yes' : undefined} data-retiring-day={square.date} data-retiring-state={square.state} role="img" aria-label="{row.sourceId} on {square.label}"></span>
								{/each}
								{#if row.dwellFrom !== null}<span class="dwell" data-retiring-dwell-rule style="grid-column: {row.dwellFrom} / -1"></span>{/if}
							</div>
						{/if}
						<p class="notes" data-retiring-readout>{row.readout}</p>
					</li>
				{/each}
			</ol>
			{#if strip.hidden}<p class="notes" data-retiring-more>{strip.hidden} more sources are under the mark, none closer to retiring than the last row here.</p>{/if}
			{#if strip.dates.length}
				<div class="axis" style="inline-size: {drawing.cell.width}px; grid-template-columns: repeat({strip.dates.length}, {drawing.cell.cell}px); gap: {drawing.cell.gap}px">
					{#each drawing.axis as tick (tick.column)}<span style="grid-column: {tick.column}; transform: {tick.column === strip.dates.length ? 'translateX(-100%)' : 'none'}" data-day-axis data-retiring-axis={tick.column}>{tick.text}</span>{/each}
				</div>
				<ul class="key"><li><span class="square" data-retiring-state="at-or-above"></span>at or above the mark</li><li><span class="square" data-retiring-state="under"></span>under the mark</li><li><span class="square" data-retiring-state="nothing"></span>it decided nothing that day</li></ul>
			{:else}<p class="notes" data-retiring-no-strip>The run recorded no day-by-day shares, so there is no strip to draw. Its recorded shares remain useful.</p>{/if}
			{#if drawing.records.length}<ChartReadout readout={drawing.records[selected ?? drawing.resting] ?? null} resting={selected === null} name="source-yield" maxShare={readoutMaxShare} restingNote={strip.dates.length === 1 ? ', its one recorded day' : ', its newest day'} hint={strip.dates.length === 1
				? 'Point at a square to read it. Arrow keys move between sources. Escape returns to the first source.'
				: "Point at a square to read it. Left and Right step through a source's days, Up and Down move between sources, Escape returns to rest."}/>{/if}
			{#if strip.unjudged.length}
				<p class="notes" data-retiring-unjudged-lead>Not judged yet — under one or both evidence floors, so no countdown may be drawn. The record is {strip.completeDates} complete days; a source needs {strip.minCompleteDays} complete days plus {strip.minDecisions} decisions of its own.</p>
				<ol class="source-rows" data-retiring-unjudged>
					{#each strip.unjudged as row (row.sourceId)}
						<li data-retiring-unjudged-row={row.sourceId}><p>{row.title} <small data-source-note-id>{row.sourceId}</small></p><p data-retiring-cell="bar">not judged yet</p>
							{#if row.squares.length}<div class="squares" data-retiring-strip={row.sourceId} style="grid-template-columns: repeat({strip.dates.length}, {drawing.cell.cell}px); gap: {drawing.cell.gap}px">
								{#each row.squares as square (square.date)}<span class="square" style="block-size: {drawing.cell.cell}px" data-readout-at={drawing.index.get(`${row.sourceId}|${square.date}`)} data-retiring-day={square.date} data-retiring-state={square.state} role="img" aria-label="{row.sourceId} on {square.label}"></span>{/each}
							</div>{/if}<p class="notes" data-retiring-readout>{row.readout}</p>
						</li>
					{/each}
				</ol>
				{#if strip.unjudgedHidden}<p class="notes" data-retiring-unjudged-more>{strip.unjudgedHidden} more sources are not judged yet, none closer to its floors than the last row here.</p>{/if}
			{/if}
		</div>
	{/if}
</VoicesPanel>
<style>
	.source-rows { list-style: none; padding: 0; margin: 0; }
	.source-rows li { padding-block: var(--space-3); border-block-end: 1px solid var(--color-rule); }
	.squares { display: grid; inline-size: max-content; max-inline-size: 100%; margin-block-start: var(--space-2); }
	.square { display: inline-block; min-inline-size: 4px; inline-size: 100%; border-radius: 1px; }
	.square[data-retiring-state='under'] { background: var(--chart-1); }
	.square[data-retiring-state='at-or-above'] { background: var(--chart-3); }
	.square[data-retiring-state='nothing'] { border: 1px dashed var(--chart-axis); }
	.dwell { border-block-end: 2px solid var(--chart-marker); margin-block-start: 2px; }
	.axis { display: grid; font-size: var(--text-xs); color: var(--color-text-secondary); }
	.axis span { white-space: nowrap; }
	.key { display: flex; flex-wrap: wrap; gap: var(--space-3); padding: 0; list-style: none; font-size: var(--text-xs); }
	.key .square { inline-size: 10px; block-size: 10px; margin-inline-end: 4px; }
</style>
