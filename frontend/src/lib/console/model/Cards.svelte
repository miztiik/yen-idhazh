<script lang="ts">
	import type { ModelDay } from '../../server/model-work';
	import type { ModelRule } from '../../charts/d3/model-rule';
	import KpiCard from '../../components/KpiCard.svelte';
	import Sparkline from '../../components/Sparkline.svelte';
	import { buildCardTrends } from '../model-cards';
	import { RECORDED } from '../eval-instruments';
	import { cardColumns, cardValue, cardText, cardTrendDays, cardReadState, cardModelRule, type CardReads } from './cards';
	import type { ChartConfig } from '../../server/config';
	import { nameSpan } from '../span-words';
	import { formatNumber } from '$lib/number-format';
	let { days, reads, instruments, start, end, rule, chart, windowDays }: {
		days: readonly ModelDay[] | null;
		reads?: CardReads;
		instruments: readonly { date: string; recorded: Readonly<Record<string, number | null>> }[];
		start: string; end: string; rule: ModelRule; chart: ChartConfig; windowDays: number;
	} = $props();
	const ordered = $derived((days ?? []).filter((day) => day.date >= start && day.date <= end).toSorted((a, b) => a.date.localeCompare(b.date)));
	const newest = $derived(ordered.at(-1));
	const empty = $derived(days === null || reads === undefined ? 'missing' : cardReadState(reads, { start, end }));
	const trends = $derived(buildCardTrends(cardColumns.map((c) => c.key), cardTrendDays(ordered), cardValue, []));
	const extra = RECORDED.filter((i) => i.id === 'coherence');
	const ruleContext = $derived('changes' in rule && rule.changes.length > 0 ? 'model-card-changes' : undefined);
</script>

<div data-model-cards data-model-cards-day={newest?.date} data-model-cards-from={start} data-model-cards-to={end} data-windowed="model-cards" data-window-days={windowDays}>
	<p data-model-cards-note data-model-newest={newest?.date} data-window-days={windowDays}
		data-comparison="each card's newest day against its last 14 days">
		{#if newest}Newest measured day: <time datetime={newest.date}>{newest.date} UTC</time>. {/if}
		Mini charts and percentage changes use up to the last 14 days in this window.
		Point at or focus a line to inspect it; Left and Right step by day, Escape returns to the newest.
		Missing readings are not zero.
	</p>
	{#if newest === undefined}
		<p data-model-cards-empty={empty} data-lede>{empty === 'missing' ? 'The build-time model record is unavailable in this window.' : 'No model readings were recorded in this window.'}</p>
		<div data-model-rule="no" data-model-rule-name="model-cards" data-model-rule-none="There are no measured card days on which to place a change." data-readout-none="No model-card readings were available."></div>
	{:else}
		<div class="cards" data-chart="cards" aria-label="The newest model readings and their measured daily history">
			{#each cardColumns as column, index (column.key)}
				{@const cardTrend = trends.get(column.key)}
				{@const activeRule = cardModelRule(rule, cardTrend?.marks.dates ?? [])}
				<KpiCard label={column.label} value={cardText(cardValue(newest, column.key), column.key)}
					line={column.line} polarity={column.polarity} lede={index === 0} rule={activeRule}
					movement={cardTrend?.marks.movement ?? null} ruleName={`card-${column.key}`}
					ruleRange={{ from: cardTrend?.marks.dates[0] ?? newest.date, to: cardTrend?.marks.dates.at(-1) ?? newest.date }}
					note={column.key === 'per-item' && newest.perItemCutMs !== null ? `${cardText(newest.perItemCutMs, column.key)} when cut short` : null}
					{windowDays}>
					{#snippet trend()}
						{#if cardTrend !== undefined && !cardTrend.marks.empty}
							<Sparkline marks={cardTrend.marks} width={188} height={22}
								label={column.label} series={{ label: column.label, format: (value) => cardText(value, column.key) }}
								strip={{ name: `model-${column.key}`, maxShare: chart.readout_max_share, hint: '', compact: true, ruleContext }}
								modelRule={activeRule} />
						{:else}
							<p class="card-history-empty" data-model-card-history-empty={column.key}>{cardTrend?.marks.dates.length
								? 'Only one measured day; no trend yet.' : 'No measured days for this card.'}</p>
						{/if}
					{/snippet}
				</KpiCard>
			{/each}
		</div>
	{/if}
	{#if 'declined' in rule}
		<p data-model-cards-rule-note>{rule.declined}</p>
	{:else}
		{#if rule.note !== null}<p data-model-cards-rule-note>{rule.note}</p>{/if}
		{#if rule.changes.length > 0}
			<details class="console-disclosure" data-model-cards-rule-history data-window-days={windowDays}>
				<summary class="console-summary" id={ruleContext}>Settings changes in {nameSpan(windowDays)}</summary>
				<p>This history covers {start} through {end} UTC, including days before the mini charts.
					Markers stay on measured chart days.</p>
				<ul>
					{#each rule.changes as change (`${change.date}-${change.kind}`)}
						<li data-model-card-change={change.date} data-model-card-change-kind={change.kind}>
							<time datetime={change.date}>{change.date} UTC</time> - {change.words}.
						</li>
					{/each}
				</ul>
			</details>
		{/if}
	{/if}
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
						{#each cardColumns as column}<td data-model-cell={column.key}>{cardText(cardValue(day, column.key), column.key)}
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
		</div>
	</details>
</div>

<style>
	.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(220px, 100%), 1fr)); gap: var(--space-3); }
	.card-history-empty { font-size: var(--console-small-size); line-height: var(--console-small-leading); color: var(--color-text-secondary); }
	details { overflow-x: auto; }
	table { inline-size: 100%; border-collapse: collapse; font-size: var(--text-xs); }
	th, td { padding: var(--space-2); text-align: right; overflow-wrap: anywhere; border-bottom: 1px solid var(--color-rule); }
</style>
