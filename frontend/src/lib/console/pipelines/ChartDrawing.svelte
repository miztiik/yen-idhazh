<script lang="ts">
	import { chartRule, chartFlow, visualsPublished, minutesText, coverageText } from './chart-drawing';
	import TargetBar from '$lib/components/TargetBar.svelte';
	import Sparkline from '$lib/components/Sparkline.svelte';
	import { movementVerdict } from '$lib/charts/theme';
	import type { TargetSense } from '$lib/charts/targetbar';
	import { flow as placeFlow } from '$lib/charts/d3/flow';
	import Flow from '$lib/charts/d3/Flow.svelte';
	import { emptyState } from '$lib/charts/d3/empty';
	import { frame, MARGIN, observeWidth } from '$lib/charts/frame';
	import { dailyFiguresSummary, dailyFiguresRows } from '$lib/console/daily-figures';
	import type { ChartDay } from '$lib/server/chart-days';
	import type { ConsoleConfig } from '$lib/server/config';
	let { days, windowDays, knobs }: { days: ChartDay[]; windowDays: number; knobs: ConsoleConfig } = $props();
	let measured = $state<number | null>(null);
	const thresholds = $derived({ ruleDays: knobs.chart_rule_days, minutesTarget: knobs.chart_minutes_target, coveragePct: knobs.chart_coverage_pct });
	const rule = $derived(chartRule(days, thresholds, windowDays));
	const flow = $derived(chartFlow(days));
	const geometry = $derived(placeFlow(flow.steps.map((step, index) => ({
		label: step.label, arrived: step.value, left: flow.steps[index + 1]?.value ?? step.value,
		drops: step.lost === null ? [] : [{ label: step.lost.label, count: step.lost.value }]
	})), { narrow: measured !== null && measured < 700, frame: frame(measured ?? knobs.chart_width, 260, { ...MARGIN, right: 170 }), nodeWidth: 12, nodeGap: 34 }));
	const minutes = (value: number | null) => value === null ? '-' : value.toFixed(1);
</script>
<div use:observeWidth={(width) => measured = width} data-windowed="chart-drawing" data-window-days={windowDays}>
	{#if days.length > 0}<p data-lede class="lede">{visualsPublished(days)} visuals published.</p>{/if}
	{#if !rule.narrow}<p data-charts-verdict>{rule.verdict}</p>{/if}
	{#if days.length === 0}<p data-empty="missing">The private chart-drawing day records are unavailable.</p>
	{:else if flow.empty}<p data-empty="quiet">{flow.reason}</p>{/if}
	<p data-comparison="Visuals published against articles that reached drawing.">Visuals published against articles that reached drawing.</p>
	<p data-charts-rule>Over {thresholds.ruleDays} days with the chart-only gate on, chart drawing is retired above {thresholds.minutesTarget} minutes per visual or below {thresholds.coveragePct}% coverage.</p>
	<div data-charts="rule">
		{#if rule.narrow}<p data-window-too-narrow="chart-drawing">The rule reads {thresholds.ruleDays} days. Widen the window to see it.</p>
		{:else}
			<div class="auto-grid">
				<div data-rule-figure="minutes">
				<TargetBar marks={rule.minutesMarks} label="Minutes per visual" valueText={rule.minutes === null ? 'Not measured' : minutesText(rule.minutes)}
					targetText="Retired above {thresholds.minutesTarget}, on the median day." emptyNote="No minutes are on record." />
				<Sparkline marks={rule.minutesTrend} series={{ label: 'Minutes per visual', format: minutesText }}
					strip={{ name: 'chart-minutes', maxShare: 1, hint: 'Point at the line to read a day.' }} width={220} height={30} label="Minutes per visual across the window" />
				{@render movement(rule.minutesTrend.movement, rule.minutesMarks.sense, 'minutes')}
				</div><div data-rule-figure="coverage">
				<TargetBar marks={rule.coverageMarks} label="Published articles with a visual" valueText={rule.coverage === null ? 'Not measured' : coverageText(rule.coverage)}
					targetText="Retired below {thresholds.coveragePct}%, on the median day." emptyNote="No published item carries a chart reading." />
				<Sparkline marks={rule.coverageTrend} series={{ label: 'Articles with a visual', format: coverageText }}
					strip={{ name: 'chart-coverage', maxShare: 1, hint: 'Point at the line to read a day.' }} width={220} height={30} label="Articles with a visual across the window" />
				{@render movement(rule.coverageTrend.movement, rule.coverageMarks.sense, 'coverage')}
				</div>
			</div>
		{/if}
	</div>
	<div data-flow="chart"><Flow {geometry} empty={emptyState('quiet', flow.reason ?? 'No visual-planner counts are recorded.')}
		name="chart-drawing" label="Where the visual planner's items went" width={knobs.chart_width} height={260} />
	</div>
	<p data-flow-shares>Every share is of the items the visual planner reached.</p>
	<details data-charts="daily" data-daily-figures="pipelines" data-daily-rows={days.length}>
		<summary data-charts-toggle>{dailyFiguresSummary(windowDays)}</summary>
		<p>{dailyFiguresRows(windowDays)} A dash means no minutes are on record.</p>
		<div class="console-table" data-charts="table"><table>
			<thead><tr><th>Day</th><th>Reached</th><th>Asked the model</th><th>Visuals drafted</th><th>Visuals published</th><th>Items published</th><th>Minutes spent</th><th>Minutes per visual</th></tr></thead>
			<tbody>{#each days as day (day.date)}<tr data-chart-day={day.date}>
				<td>{day.date}</td><td data-charts-cell="reached">{day.reached}</td><td data-charts-cell="asked">{day.asked}</td><td data-charts-cell="drafted">{day.drafted}</td>
				<td data-charts-cell="published">{day.published}</td><td data-charts-cell="items">{day.items}</td><td data-charts-cell="minutes">{minutes(day.plannerMinutes)}</td><td data-charts-cell="per-chart">{minutes(day.minutesPerChart)}</td>
			</tr>{/each}</tbody>
		</table></div>
	</details>
</div>
{#snippet movement(value: number | null, sense: TargetSense, name: string)}
	{#if value !== null}<p data-rule-move={name}><span data-movement={value.toFixed(4)} data-polarity={sense}
		data-movement-verdict={movementVerdict(value, sense)} data-movement-paint="color">{value >= 0 ? '+' : ''}{Math.round(value * 100)}%</span> across this window</p>{/if}
{/snippet}
<style>.lede { font-size: var(--text-2xl); }</style>
