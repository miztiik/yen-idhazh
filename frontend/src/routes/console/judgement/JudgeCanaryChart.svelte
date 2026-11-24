<script lang="ts">
	import Panel from '$lib/components/Panel.svelte';
	import DiagnosticGrid from '$lib/charts/d3/DiagnosticGrid.svelte';
	import { diagnosticGrid, type GridDiagnostic } from '$lib/charts/d3/diagnosticGrid';
	import { factsOf } from '$lib/charts/readout';
	import { judgeCanaries } from '$lib/console/judge-observations';
	import type { Row } from '$lib/data/ledger';
	import { longDate } from '$lib/format';
	import { numberFormatter } from '$lib/number-format';
	import type { ChartConfig } from '$lib/server/config';
	import { OUTCOME_STYLE } from './judge-trial-style';

	let { selected, detail, dayNote, chart, asChart = true }: {
		selected: string; detail: Row | null; dayNote: string; chart: ChartConfig; asChart?: boolean;
	} = $props();

	const name = 'judge-canaries';
	const label = 'Canary answers by order';
	const number = $derived(numberFormatter(chart.number_format));
	const exact = (n: number) => number(n, { exact: true });
	const canaries = $derived(detail === null ? null : judgeCanaries(detail));
	const answerColumns = [
		{ key: 'expected', label: 'Expected', absent: 'No saved key' },
		{ key: 'forward', label: 'File order', absent: 'No answer' },
		{ key: 'swapped', label: 'Swapped', absent: 'No answer' }
	] as const;
	const columns = [...answerColumns, { label: 'Outcome' }];
	const tokens = { YES: OUTCOME_STYLE.yes.token, NO: OUTCOME_STYLE.no.token, UNCLEAR: OUTCOME_STYLE.unclear.token };
	const grid = $derived.by(() => {
		const items = canaries?.items ?? [];
		const rows = items.map(({ id }) => ({ label: id }));
		const data = items.map((item): GridDiagnostic[] => [
			...answerColumns.map(({ key, label, absent }) => {
				const value = item[key];
				const text = value ?? absent;
				return {
					text,
					paint: value === null ? null : `color-mix(in oklab, var(${tokens[value]}) calc(100% * var(--chart-spread-mix)), var(--color-surface))`,
					facts: factsOf(item.id, [{ label, value: text }], absent)
				};
			}),
			{
				text: item.outcome, paint: 'var(--color-surface)',
				emphasized: item.outcome !== 'Matched' && item.outcome !== 'Not graded',
				edge: item.outcome === 'Split' ? `var(${OUTCOME_STYLE.split.token})` : undefined,
				facts: factsOf(item.id, [{ label: 'Outcome', value: item.outcome }], 'Not graded')
			}
		]);
		return diagnosticGrid(rows, columns, data);
	});
</script>

{#snippet summary()}
	{#if canaries && canaries.items.length}
		{#if canaries.graded}
			<p><strong>{exact(canaries.matches)} of {exact(canaries.items.length)} pairs matched</strong> the saved agent-labelled key.</p>
			<p>Cohen's kappa:
				{#if canaries.kappa !== null && canaries.eligible !== null}
					{number(canaries.kappa, { si: false })} across {exact(canaries.eligible)} {canaries.eligible === 1 ? 'pair' : 'pairs'}.
				{:else if canaries.eligible !== null && canaries.eligible < canaries.items.length}
					Not measured: only {exact(canaries.eligible)} of {exact(canaries.items.length)} pairs agreed in both orders.
				{:else if canaries.eligible === canaries.items.length}
					Not measured: the chance-adjusted denominator was zero.
				{:else}
					Not recorded.
				{/if}
			</p>
		{:else}
			<p>No saved key. The observed answers are not graded.</p>
		{/if}
	{:else if detail}
		<p>No canary evidence recorded for this attempt.</p>
	{:else}
		<p>{dayNote}</p>
	{/if}
{/snippet}

{#if asChart}
	<Panel title={label} heading="h3" wide>
		<div data-judge-digest={selected} data-panel-question="Which known-answer pairs matched or changed when reversed?"
			data-model-rule="no" data-model-rule-name={name} data-model-rule-none="The canaries use the key saved with this attempt.">
			<p data-lede>{longDate(selected)} UTC.</p>
			{@render summary()}
			{#if grid !== null}
				<DiagnosticGrid drawing={grid} {name} {label} corner="Known pair" labels tileRows maxShare={chart.readout_max_share} />
			{/if}
		</div>
	</Panel>
{:else}
	<section aria-labelledby="judge-known-answers">
		<h4 id="judge-known-answers">Known-answer pairs</h4>
		{@render summary()}
		{#if canaries?.items.length}
			<ul class="known-answers">
				{#each canaries.items as item (item.id)}
					<li>
						<strong>{item.id}</strong>
						<span>{#if item.expected}Expected {item.expected} &middot; {/if}
							File order: {item.forward ?? 'no answer'} &middot; Swapped: {item.swapped ?? 'no answer'}</span>
						<span class="outcome">{item.outcome}</span>
					</li>
				{/each}
			</ul>
		{/if}
	</section>
{/if}

<style>
	h4, p { margin: 0 0 var(--space-2); overflow-wrap: anywhere; }
	.known-answers { list-style: none; margin: 0; padding: 0; }
	.known-answers li {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr) auto;
		align-items: baseline;
		gap: var(--space-1) var(--space-3);
		padding-block: var(--space-2);
		border-block-start: 1px solid var(--color-rule);
		font-size: var(--console-small-size);
		line-height: var(--console-small-leading);
		overflow-wrap: anywhere;
	}
	.outcome { color: var(--color-text-secondary); }
</style>
