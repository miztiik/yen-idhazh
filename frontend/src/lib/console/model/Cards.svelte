<script lang="ts">
	import type { ModelDay } from '../../server/model-work';
	import type { ModelRule } from '../../charts/d3/model-rule';
	import KpiCard from '../../components/KpiCard.svelte';
	import Sparkline from '../../components/Sparkline.svelte';
	import { buildCardTrends } from '../model-cards';
	import { FLAGS, RECORDED } from '../eval-instruments';
	import { cardColumns, cardValue, cardText, cardTrendDays } from './cards';
	import type { ChartConfig } from '../../server/config';
	import { completeModelRule } from './model-rule';
	import { nameSpan } from '../span-words';
	import { formatNumber } from '$lib/number-format';
	let { days, instruments, start, end, rule, checkerRule, chart, windowDays }: {
		days: readonly (ModelDay & { determinismViolations: number | null })[] | null;
		instruments: readonly { date: string; recorded: Readonly<Record<string, number | null>> }[];
		start: string; end: string; rule: ModelRule; checkerRule: ModelRule; chart: ChartConfig; windowDays: number;
	} = $props();
	const ordered = $derived((days ?? []).filter((day) => day.date >= start && day.date <= end).toSorted((a, b) => a.date.localeCompare(b.date)));
	const newest = $derived(ordered.at(-1));
	const trends = $derived(buildCardTrends(cardColumns.map((c) => c.key), cardTrendDays(ordered), cardValue, []));
	const extra = $derived(RECORDED.filter((i) => ['self_repetition', 'coherence', 'semantic_coverage'].includes(i.id)));
</script>

<div data-model-cards data-model-cards-day={newest?.date} data-windowed="model-cards" data-window-days={windowDays}>
	{#if newest === undefined}
		<p data-model-cards-empty={days === null ? 'missing' : 'quiet'} data-lede>{days === null ? 'The build-time model record is unavailable.' : 'No model work was recorded in this window.'}</p>
		<div data-model-rule="no" data-model-rule-name="model-cards" data-model-rule-none="There are no measured card days on which to place a change." data-readout-none="No model-card readings were available."></div>
	{:else}
		<div class="cards" data-chart="cards" aria-label="The newest model readings and their measured daily history">
			{#each cardColumns as column, index (column.key)}
				{@const cardTrend = trends.get(column.key)}
				{@const activeRule = completeModelRule(column.key === 'not-sure' ? checkerRule : rule, cardTrend?.marks.dates ?? [])}
				<div data-instrument={column.key === 'determinism' ? 'determinism_violation' : undefined} data-instrument-slot={column.key === 'determinism' ? 'model-cards' : undefined}>
				<KpiCard label={column.label} value={cardText(cardValue(newest, column.key), column.key)}
					line={column.line} polarity={column.polarity} lede={index === 0} rule={activeRule}
					movement={cardTrend?.marks.movement ?? null} ruleName={`card-${column.key}`}
					ruleRange={{ from: cardTrend?.marks.dates[0] ?? newest.date, to: cardTrend?.marks.dates.at(-1) ?? newest.date }}
					note={column.key === 'per-item' ? (newest.perItemCutMs === null ? null : `${cardText(newest.perItemCutMs, column.key)} when cut short`) :
						['not-sure', 'unsupported', 'hedge', 'copied', 'determinism'].includes(column.key) && newest.summaries !== null ? `of ${newest.summaries} ${newest.summaries === 1 ? 'summary' : 'summaries'}` : null}
					{windowDays}>
					{#snippet trend()}
						{#if cardTrend !== undefined}
							<Sparkline marks={cardTrend.marks} width={188} height={22}
								label={column.label} series={{ label: column.label, format: (value) => cardText(value, column.key) }}
								strip={{ name: `model-${column.key}`, maxShare: chart.readout_max_share, hint: 'Point at a day to read it.' }}
								modelRule={activeRule} />
						{/if}
					{/snippet}
				</KpiCard>
				</div>
			{/each}
		</div>
	{/if}
	<p data-model-cards-note data-model-newest={newest?.date} data-window-days={windowDays}>The cards show the newest measured day in this window. A missing reading is not measured, not zero.</p>
	<p data-comparison="each card's newest day against its last 14 days">Each card's newest day against its last 14 days.</p>
	<p>Nothing acts on these numbers.</p>
	<details class="console-disclosure" data-model-table-control data-daily-figures="model" data-window-days={windowDays}>
		<summary class="console-summary">{windowDays === 1 ? 'Show these figures for this one day' : `Show these figures day by day, over these ${windowDays} days`}</summary>
		<div class="console-table" data-eval-panel="daily-figures" data-windowed="daily-figures" data-window-days={windowDays} data-model="table">
			<table data-model-table>
				<caption>One row per recorded day in {nameSpan(windowDays)}. Missing readings are not measured.</caption>
				<thead><tr><th scope="col">Day</th>{#each cardColumns as column}<th scope="col">{column.label}</th>{/each}
					{#each extra as instrument}<th scope="col">{instrument.label}</th>{/each}</tr></thead>
				<tbody>{#each ordered.toReversed() as day (day.date)}
					<tr data-model-day={day.date}><th scope="row">{day.date}</th>
						{#each cardColumns as column}<td data-model-cell={column.key} data-instrument={column.key === 'determinism' ? 'determinism_violation' : undefined}>{cardText(cardValue(day, column.key), column.key)}
							{#if column.key === 'per-item' && day.perItemCutMs !== null}<span data-model-aside="per-item">{cardText(day.perItemCutMs, column.key)} when cut short</span>{/if}
						</td>{/each}
						{#each extra as instrument}
							{@const value = instruments.find((entry) => entry.date === day.date)?.recorded[instrument.id] ?? null}
							<td data-instrument={instrument.id}>{value === null ? 'not measured' : instrument.unit === 'cosine'
								? formatNumber(value, chart.number_format, { si: false })
								: `${formatNumber(value, chart.number_format, { si: false })}%`}</td>
						{/each}
					</tr>
				{/each}</tbody>
			</table>
			{#each extra as instrument}<p><strong>{instrument.label}</strong> {instrument.note}</p>{/each}
			<p>{FLAGS.find((flag) => flag.id === 'determinism_violation')?.note}</p>
		</div>
	</details>
</div>

<style>
	.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(220px, 100%), 1fr)); gap: var(--space-3); }
	details { overflow-x: auto; }
	table { inline-size: 100%; border-collapse: collapse; font-size: var(--text-xs); }
	th, td { padding: var(--space-2); text-align: right; overflow-wrap: anywhere; border-bottom: 1px solid var(--color-rule); }
</style>
