<script lang="ts">
	/** How much of each call's prompt the model server already had cached, one stacked bar a UTC day.
	 *
	 * Two charts, summary first and label second, because the calls move
	 * independently and one scale would hide the summary call's step. Each bar
	 * runs 0 to 100 percent of that day's prompt tokens: the cached share fills the
	 * bottom in the call's own colour and the remainder above it is the same colour
	 * tinted, so the bar reads as one prompt split in two. A day with no complete
	 * reading is a gap, never an empty prompt.
	 */
	import Panel from '$lib/components/Panel.svelte';
	import DateSeries from '$lib/charts/d3/DateSeries.svelte';
	import { dateSeries, type SeriesInput } from '$lib/charts/d3/dateSeries';
	import { emptyState } from '$lib/charts/d3/empty';
	import { completeModelRule } from '$lib/charts/d3/model-rule';
	import { spreadPaint } from '$lib/charts/d3/spread-paint';
	import { chartWidth, observeWidth } from '$lib/charts/frame';
	import { useChartFrame } from '$lib/charts/label-context';
	import { readoutOf } from '$lib/charts/readout';
	import type { ChartToken } from '$lib/charts/theme';
	import { SERIES_TOKENS } from '$lib/console/series-tokens';
	import { settingsRules } from '$lib/console/settings-moved';
	import { nameSpan } from '$lib/console/span-words';
	import { shortDate } from '$lib/format';
	import { formatNumber } from '$lib/number-format';
	import { reuseDays, type ReuseCall } from './prompt-reuse';
	import type { ConsoleShell } from '$lib/console/band';
	import type { Row } from '$lib/data/ledger';
	import type { ChartConfig } from '$lib/server/config';

	let { rows, title, chart, shell, start, end, windowDays }: {
		rows: readonly Row[];
		title: string;
		chart: ChartConfig;
		shell: ConsoleShell;
		start: string;
		end: string;
		windowDays: number;
	} = $props();

	const CALLS = [
		{ call: 'summary', name: 'Summary call', token: SERIES_TOKENS['summary-call'] },
		{ call: 'label', name: 'Label call', token: SERIES_TOKENS['label-call'] }
	] as const satisfies readonly { call: ReuseCall; name: string; token: ChartToken }[];
	/** A share runs 0 to 100, and two ticks put the gridlines at 0, 50 and 100. */
	const DOMAIN: [number, number] = [0, 100];
	const VALUE_TICKS = 2;
	/** The share of a day's column left empty beside its bar. */
	const PADDING = 0.2;
	const comparison = "Tokens the model already had cached against tokens it read fresh, as a share of each call's prompt, one bar a day";

	const frame = useChartFrame(() => chart);
	let width = $state<number | null>(null);
	const box = $derived(frame(chartWidth(width, chart.width_px), chart.height_px));
	const numberFormat = $derived(chart.number_format);
	const rule = $derived(settingsRules(shell, { from: start, to: end }, 'none'));
	const dates = $derived([...new Set(rows.flatMap((row) => typeof row.date === 'string' ? [row.date] : []))].sort());

	const percent = (share: number) => `${formatNumber(share, numberFormat, { si: false })}%`;
	const count = (value: number) => formatNumber(value, numberFormat, { exact: true, si: false });
	/** What is left of 100 once the cached share is printed, written to the same decimal places, so the two printed shares total 100. */
	const rest = (share: number) => {
		const printed = Number(share.toPrecision(numberFormat.significant_digits));
		const left = 100 - printed;
		const places = (String(printed).split('.')[1] ?? '').length;
		return `${formatNumber(left, { ...numberFormat, significant_digits: String(Math.trunc(left)).length + places }, { si: false })}%`;
	};

	const reads = $derived(CALLS.map((one) => {
		const days = reuseDays(rows, one.call);
		return { ...one, byDate: new Map(days.map((day) => [day.date, day])), latest: days.at(-1)?.date ?? null };
	}));
	const newest = $derived(reads.flatMap((one) => one.latest === null ? [] : [one.latest]).sort().at(-1) ?? null);
	const lede = $derived.by(() => {
		const shown = reads.flatMap((one) => {
			const share = newest === null ? undefined : one.byDate.get(newest)?.share;
			return share === undefined ? [] : [{ call: one.call, share }];
		});
		if (newest === null || shown.length === 0) return 'No call recorded both its prompt and its cached tokens in this window.';
		const [first, second] = shown;
		const said = `${percent(first.share)} of the ${first.call} call's prompt tokens were already cached on ${shortDate(newest)}`;
		return shown.length === reads.length
			? `${said}, and ${percent(second.share)} of the ${second.call} call's.`
			: `${said}; the ${reads.find((one) => one.call !== first.call)!.call} call has no reading that day.`;
	});

	const charts = $derived(reads.map(({ call, name, token, byDate }) => {
		const readings = dates.map((date) => ({ date, day: byDate.get(date) }));
		const tint = spreadPaint(token);
		const series: SeriesInput[] = [
			{ label: 'Cached', token, points: readings.map(({ date, day }) => ({ date, value: day?.share ?? null })) },
			{ label: 'Read fresh', token, fill: tint, points: readings.map(({ date, day }) =>
				({ date, value: day === undefined ? null : 100 - day.share })) }
		];
		const geometry = dateSeries(series, {
			frame: box, stacked: true, density: chart.tick_density, valueTicks: VALUE_TICKS, padding: PADDING,
			rule: completeModelRule(rule, dates), domain: DOMAIN, number_format: numberFormat
		});
		const readout = geometry === null ? null : readoutOf({
			type: 'dateSeries',
			columns: dates.map(shortDate),
			series: [
				{ label: 'Cached', swatch: `var(${token})`, format: percent,
					values: readings.map(({ day }) => day?.share ?? null) },
				{ label: 'Read fresh', swatch: tint, format: percent,
					values: readings.map(({ day }) => day === undefined ? null : rest(day.share)) }
			],
			events: { lines: readings.map(({ day }) => day === undefined ? [] : [
				{ label: 'Prompt tokens', value: count(day.input), swatch: null },
				{ label: 'Articles', value: count(day.articles), swatch: null }
			]) },
			notMeasured: 'Not recorded.',
			resting: 'last'
		});
		return {
			call, name, geometry, readout,
			empty: emptyState('quiet', `No ${call} call recorded both its prompt and its cached tokens in this window.`)
		};
	}));
</script>

<div data-windowed="machine-prompt-reuse" data-window-days={windowDays}>
	<Panel id="prompt-reuse" {title} heading="h3"
		note="Read from the published record when you open this page - over {nameSpan(windowDays)}.">
		<div data-panel-question="is it working">
			<p class="lede" data-lede>{lede}</p>
			<p data-comparison={comparison}>{comparison}.</p>
			<div class="halves auto-grid">
				{#each charts as one (one.call)}
					<div>
						<h4>{one.name}</h4>
						<div use:observeWidth={(px) => (width = px)}>
							<DateSeries geometry={one.geometry} readout={one.readout} empty={one.empty}
								name="prompt-reuse-{one.call}"
								label="{one.name}: cached share of each day's prompt tokens, one bar a day"
								width={box.width} height={box.height} readoutMaxShare={chart.readout_max_share} />
						</div>
					</div>
				{/each}
			</div>
		</div>
	</Panel>
</div>

<style>
	.lede { font-size: var(--console-page-title-size); line-height: var(--console-page-title-leading); font-weight: var(--console-page-title-weight); }
	.halves > div { min-width: 0; }
	h4 { font-size: var(--console-body-size); line-height: var(--console-body-leading); margin-block: var(--console-control-gap); }
</style>
