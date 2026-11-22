<script lang="ts">
	/** How much of each call's prompt the model server already had cached, one stacked bar a UTC day.
	 *
	 * Both calls share a UTC calendar and the same colours for cached and fresh
	 * tokens. A change date can have a rule but no bar: the two records are independent.
	 */
	import Panel from '$lib/components/Panel.svelte';
	import DateSeries from '$lib/charts/d3/DateSeries.svelte';
	import { dateSeries, type SeriesInput } from '$lib/charts/d3/dateSeries';
	import { emptyState } from '$lib/charts/d3/empty';
	import { chartWidth, observeWidth } from '$lib/charts/frame';
	import { useChartFrame } from '$lib/charts/label-context';
	import { readoutOf } from '$lib/charts/readout';
	import { daysInWindow } from '$lib/charts/viewport';
	import { SERIES_TOKENS } from '$lib/console/series-tokens';
	import type { Range } from '$lib/console/queries/window';
	import { settingsRules } from '$lib/console/settings-moved';
	import { shortDate } from '$lib/format';
	import { formatNumber } from '$lib/number-format';
	import { reuseDays } from './prompt-reuse';
	import type { ConsoleShell } from '$lib/console/band';
	import type { Row } from '$lib/data/ledger';
	import type { ChartConfig } from '$lib/server/config';

	let { rows, title, chart, shell, range, windowDays }: {
		rows: readonly Row[];
		title: string;
		chart: ChartConfig;
		shell: ConsoleShell;
		range: Range;
		windowDays: number;
	} = $props();

	const CALLS = [
		{ call: 'summary', name: 'Summary call' },
		{ call: 'label', name: 'Label call' }
	] as const;
	const cached = SERIES_TOKENS['cached-prompt'];
	const fresh = SERIES_TOKENS['reading-prompt'];
	/** A share runs 0 to 100, and two ticks put the gridlines at 0, 50 and 100. */
	const DOMAIN: [number, number] = [0, 100];
	const VALUE_TICKS = 2;
	/** The share of a day's column left empty beside its bar. */
	const PADDING = 0.2;
	const frame = useChartFrame(() => chart);
	let width = $state<number | null>(null);
	const box = $derived(frame(chartWidth(width, chart.width_px), chart.height_px));
	const numberFormat = $derived(chart.number_format);
	const rule = $derived(settingsRules(shell, range, 'none', 'this window'));
	const dates = $derived(daysInWindow({ start: range.from, end: range.to }));

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
		if (newest === null || shown.length === 0) return 'No call recorded both prompt and cached tokens.';
		const [first, second] = shown;
		const said = `${shortDate(newest)}: ${percent(first.share)} cached for the ${first.call} call`;
		return shown.length === reads.length
			? `${said}, ${percent(second.share)} for the ${second.call} call.`
			: `${said}; no ${first.call === 'summary' ? 'label' : 'summary'} reading.`;
	});

	const charts = $derived(reads.map(({ call, name, byDate }) => {
		const readings = dates.map((date) => ({ date, day: byDate.get(date) }));
		const series: SeriesInput[] = [
			{ label: 'Cached', token: cached, points: readings.map(({ date, day }) => ({ date, value: day?.share ?? null })) },
			{ label: 'Read fresh', token: fresh, points: readings.map(({ date, day }) =>
				({ date, value: day === undefined ? null : 100 - day.share })) }
		];
		const geometry = dateSeries(series, {
			frame: box, stacked: true, density: chart.tick_density, valueTicks: VALUE_TICKS, padding: PADDING,
			rule: 'declined' in rule ? rule : { changes: rule.changes, note: null },
			domain: DOMAIN, valueFormat: percent, number_format: numberFormat
		});
		const readout = geometry === null ? null : readoutOf({
			type: 'dateSeries',
			columns: dates.map(shortDate),
			series: [
				{ label: 'Cached', swatch: `var(${cached})`, format: percent,
					values: readings.map(({ day }) => day?.share ?? null) },
				{ label: 'Read fresh', swatch: `var(${fresh})`, format: percent,
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
	const hasPlot = $derived(charts.some((one) => one.geometry !== null));
</script>

<div data-windowed="machine-prompt-reuse" data-window-days={windowDays}>
	<Panel id="prompt-reuse" {title} heading="h3">
		<div data-panel-question="is it working">
			<p class="lede" data-lede>{lede}</p>
			<p data-comparison="Cached and fresh prompt tokens per call, as a share of the daily total">Each bar splits a day's measured prompt tokens into cached and read fresh.</p>
			{#if 'declined' in rule}
				<p class="settings-note">Settings change history is unavailable.</p>
			{:else}
				{#if hasPlot && rule.changes.length > 0}
					<p class="settings-note">Dashed lines mark recorded changes to the model, prompt or other settings.</p>
				{/if}
				{#if rule.note !== null}<p class="settings-note">{rule.note}</p>{/if}
			{/if}
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
	.settings-note { color: var(--color-text-secondary); font-size: var(--console-small-size); line-height: var(--console-small-leading); }
</style>
