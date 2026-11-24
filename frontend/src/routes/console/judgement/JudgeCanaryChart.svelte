<script lang="ts">
	/** Compare each saved expected verdict with the answer mix across digest dates. */
	import ChartReadout from '$lib/components/ChartReadout.svelte';
	import Panel from '$lib/components/Panel.svelte';
	import { chartWidth, MARGIN, observeWidth } from '$lib/charts/frame';
	import { useChartFrame } from '$lib/charts/label-context';
	import { columnPick, factsOf, pointerReadout, readoutMarks, readoutOf } from '$lib/charts/readout';
	import { CANARY_BANDS, CANARY_CATEGORIES, judgeCanaryDays, type CanaryDay, type CanaryGroup } from '$lib/console/judge-canaries';
	import type { JudgeReading, Verdict } from '$lib/console/judge-observations';
	import { longDate } from '$lib/format';
	import { numberFormatter } from '$lib/number-format';
	import type { ChartConfig, ConsoleConfig } from '$lib/server/config';
	import JudgeCanaryDetails from './JudgeCanaryDetails.svelte';
	import { judgeCanaryTimeline } from './judge-canary-timeline';
	import { OUTCOME_STYLE } from './judge-trial-style';

	let { calendar, selected, readings, noteFor, knobs, chart, onPick }: {
		calendar: readonly string[];
		selected: string;
		readings: ReadonlyMap<string, JudgeReading>;
		noteFor: (date: string) => string;
		knobs: ConsoleConfig;
		chart: ChartConfig;
		onPick: (date: string) => void;
	} = $props();

	const name = 'judge-canaries';
	const bands = {
		YES: OUTCOME_STYLE.yes, UNCLEAR: OUTCOME_STYLE.unclear, NO: OUTCOME_STYLE.no,
		changed: { ...OUTCOME_STYLE.split, label: 'Changed on reversal' },
		invalid: { ...OUTCOME_STYLE.refused, label: 'Invalid reply' },
		missing: { ...OUTCOME_STYLE.missing, label: 'No reply' }
	};
	const TICK = 4;
	const DOT = 2.5;
	let measured = $state<number | null>(null);
	let inspected = $state<{ date: string; expected: Verdict } | null>(null);
	const frame = useChartFrame(() => chart);
	const box = $derived(frame(chartWidth(measured, knobs.chart_width), 2 * chart.sparkline_height_px + MARGIN.top + MARGIN.bottom));
	const days = $derived(judgeCanaryDays(calendar, readings));
	const picked = $derived(calendar.indexOf(selected));
	const inspectedAt = $derived(inspected === null ? -1 : calendar.indexOf(inspected.date));
	const drawing = $derived(judgeCanaryTimeline(days, box, chart.tick_density));
	const marks = $derived(readoutMarks(drawing.centers));
	const number = $derived(numberFormatter(chart.number_format));
	const exact = (n: number) => number(n, { exact: true });
	const matches = (group: CanaryGroup) => group.expected === 0 ? 'No expected pairs'
		: `${exact(group.matched)}/${exact(group.expected)} matched${group.counts.invalid || group.counts.missing ? ' (incomplete)' : ''}`;
	const hasKey = $derived(days.some(({ record }) => record?.keyState === 'saved'));
	const shownBands = $derived(CANARY_BANDS.filter((band) => drawing.timelines.some(({ columns }) =>
		columns.some(({ segments }) => segments.some((segment) => segment.band === band)))));
	const note = (day: CanaryDay) => day.record === null ? noteFor(day.date)
		: day.record.keyState === 'invalid' ? 'Saved key could not be read.'
		: 'No saved key. The observed answers are not graded.';
	const setLabel = (day: CanaryDay) => day.record?.setVersion == null ? 'Not recorded'
		: day.setChanged ? `${day.record.setVersion} (new set)` : day.record.setVersion;
	const byCategory = $derived(CANARY_CATEGORIES.map(({ expected, label }) => days.map((day) => {
		const group = day.record?.groups[expected];
		const subject = `${label} (${expected}), ${longDate(day.date)} UTC`;
		if (!group?.expected) return factsOf(subject, [], day.record?.keyState === 'saved' ? 'No expected pairs.' : note(day));
		return factsOf(subject, [
			{ label: 'Matched', value: `${exact(group.matched)}/${exact(group.expected)} (${number(100 * group.matched / group.expected, { si: false })}%)` },
			...shownBands.filter((band) => group.counts[band] > 0).map((band) => ({
				label: bands[band].label, value: exact(group.counts[band]), swatch: `var(${bands[band].token})`
			})),
			{ label: 'Canary set version', value: setLabel(day) }
		], 'Not recorded.');
	})));
	const readout = $derived(readoutOf({
		type: 'dateSeries',
		columns: calendar.map((date) => `${longDate(date)} UTC`),
		series: [
			...CANARY_CATEGORIES.map(({ expected, label }) => ({
				label, swatch: null, format: exact,
				values: days.map(({ record }) => record?.keyState === 'saved' ? matches(record.groups[expected]) : null)
			})),
			{ label: 'Canary set version', swatch: null, format: exact, values: days.map((day) =>
				day.record?.keyState === 'saved' ? setLabel(day) : null) }
		],
		notMeasured: 'Not recorded.',
		notMeasuredAt: days.map(note),
		resting: picked
	}));

	function inspect(expected: Verdict, index: number | null) {
		if (index !== null && calendar[index] !== undefined) inspected = { date: calendar[index], expected };
		else if (inspected?.expected === expected) inspected = null;
	}
</script>

<Panel title="Canaries" heading="h3" wide>
	<div class="canaries" use:observeWidth={(width) => measured = width} data-judge-digest={selected}
		data-panel-question="Which known-answer pairs matched the saved key over time?"
		data-model-rule="no" data-model-rule-name={name} data-model-rule-none="The canaries use the key saved with each attempt."
		data-windowed={name} data-window-days={calendar.length}>
		<p data-lede>Canaries are known-answer pairs judged in both story orders. A pair matches only if both replies agree with its saved answer.</p>
		{#if hasKey}
			<div class="guide" id="judge-canary-guide">
				<p data-comparison="Matched share and answer mix for the same saved pairs.">
					Match rate (0%-100%) above each daily answer mix. Blocks show all expected pairs, including invalid or missing replies.
					Open points mark incomplete replies. Dashed dividers mark a new saved set.
				</p>
				<ul class="legend" aria-label="Canary answer bands">
					{#each shownBands as band (band)}
						<li><span style:background="var({bands[band].token})" aria-hidden="true"></span>{bands[band].label}</li>
					{/each}
				</ul>
			</div>
			<div class="timelines">
				{#each drawing.timelines as timeline, category (timeline.expected)}
					{@const active = inspected?.expected === timeline.expected && inspectedAt >= 0 ? inspectedAt : picked}
					{@const chartName = `${name}-${timeline.expected.toLowerCase()}`}
					<section class="timeline" aria-labelledby={`${chartName}-title`}>
						<h4 id={`${chartName}-title`}>{timeline.label} <span>({timeline.expected})</span></h4>
						<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
						<svg viewBox="0 0 {box.width} {box.height}" width={box.width} height={box.height}
							font-size={box.labels.fontSize} role="img" aria-labelledby={`${chartName}-title`}
							aria-describedby="judge-canary-guide" tabindex="0"
							data-chart-type="canaryTimeline" data-chart-name={chartName}
							use:pointerReadout={{ marks, width: box.width, selected: active, onSelect: (index) => inspect(timeline.expected, index),
								hover: { name: chartName, readout: byCategory[category] } }}
							use:columnPick={{ marks, width: box.width, showing: active >= 0 ? active : null,
								onPick: (index) => onPick(calendar[index]) }}>
							{#if timeline.columns[picked]}
								{@const x = timeline.columns[picked].x}
								<line x1={x} x2={x} y1={box.top} y2={box.bottom + TICK}
									stroke="var(--color-focus)" data-canary-selection={selected} />
							{/if}
							{#if active !== picked && timeline.columns[active]}
								<line x1={timeline.columns[active].x} x2={timeline.columns[active].x} y1={box.top}
									y2={box.bottom} stroke="var(--chart-axis)" />
							{/if}
							<text x={box.left - TICK} y={box.top} dy="0.32em" text-anchor="end">100%</text>
							<text x={box.left - TICK} y={drawing.stripBottom} dy="0.32em" text-anchor="end">0%</text>
							<line x1={box.left} x2={box.right} y1={drawing.stripBottom} y2={drawing.stripBottom} stroke="var(--chart-grid)" />
							<line x1={box.left} x2={box.right} y1={box.bottom} y2={box.bottom} stroke="var(--chart-axis)" />
							{#each drawing.changes as change (change.date)}
								<line x1={change.x} x2={change.x} y1={box.top} y2={box.bottom}
									stroke="var(--chart-marker)" stroke-dasharray="3 3" data-canary-set-change={change.date} />
							{/each}
							{#if timeline.path}
								<path d={timeline.path} fill="none" stroke="var(--chart-measure)" stroke-width="2" data-canary-match-line />
							{/if}
							{#each timeline.columns as column (column.date)}
								{#if column.point}
									<circle cx={column.x} cy={column.point.y} r={DOT} stroke="var(--chart-measure)" stroke-width="2"
										fill={column.point.incomplete ? 'var(--color-surface)' : 'var(--chart-measure)'}
										data-canary-point={column.date} data-incomplete={column.point.incomplete} />
									<g data-canary-block={column.date}>
										{#each column.segments as part, index (part.band)}
											<rect x={column.x - drawing.blockWidth / 2} y={part.top} width={drawing.blockWidth}
												height={part.height} fill="var({bands[part.band].token})" data-canary-band={part.band} />
											{#if index > 0}
												<line x1={column.x - drawing.blockWidth / 2} x2={column.x + drawing.blockWidth / 2}
													y1={part.top} y2={part.top} stroke="var(--color-surface)" />
											{/if}
										{/each}
									</g>
								{/if}
							{/each}
							{#each drawing.ticks as tick (tick.date)}
								<text x={drawing.centers[tick.index]} y={box.bottom + box.labels.leading}
									text-anchor={tick.anchor} data-day-axis>{tick.text}</text>
							{/each}
						</svg>
					</section>
				{/each}
			</div>
			<ChartReadout {readout} at={inspectedAt >= 0 ? inspectedAt : null} {name} maxShare={chart.readout_max_share}
				restingNote=" (selected digest)" hint="Left and Right inspect dates. Click, tap or press Enter to select a digest."
				hintOne="Click, tap or press Enter to select this digest." />
		{:else if days.some(({ record }) => record !== null)}
			<p data-empty="quiet">No saved canary keys can be plotted in this window.</p>
		{/if}
		<JudgeCanaryDetails reading={days[picked]?.record ?? null} note={noteFor(selected)} {selected} format={chart.number_format} />
	</div>
</Panel>

<style>
	.canaries, .guide, .timelines { display: grid; }
	.canaries { gap: var(--space-3); }
	.guide { gap: var(--space-2); }
	.timelines { gap: var(--space-3); min-inline-size: 0; }
	.timeline { padding-block-start: var(--space-2); border-block-start: 1px solid var(--color-rule); }
	h4, p { margin: 0; overflow-wrap: anywhere; }
	h4 span, .guide { color: var(--color-text-secondary); }
	.guide { font-size: var(--console-small-size); line-height: var(--console-small-leading); }
	.legend { display: flex; flex-wrap: wrap; gap: var(--space-1) var(--space-4); list-style: none; margin: 0; padding: 0; }
	.legend li { display: inline-flex; align-items: center; gap: var(--space-1); }
	.legend span { inline-size: var(--space-3); block-size: var(--space-3); border: 1px solid var(--color-rule-strong); }
	svg { display: block; max-inline-size: 100%; }
	svg:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
	text { fill: var(--color-text-secondary); }
</style>
