<script lang="ts">
	import {
		judgeCanaries, judgeNumber, judgeProbabilityEvidence, judgeStatus, PROBABILITY_STATUS, type JudgeIdentity
	} from '$lib/console/judge-observations';
	import type { Row } from '$lib/data/ledger';
	import { longDate } from '$lib/format';
	import { numberFormatter } from '$lib/number-format';
	import type { ChartConfig } from '$lib/server/config';

	let { selected, identity, detail, dayNote, chart }: {
		selected: string;
		identity: JudgeIdentity | null;
		detail: Row | null;
		dayNote: string;
		chart: ChartConfig;
	} = $props();

	const number = $derived(numberFormatter(chart.number_format));
	const exact = (value: number) => number(value, { exact: true });
	const measuredText = (value: unknown) => {
		const n = judgeNumber(value);
		return n === null ? 'Not recorded' : number(n, { si: false });
	};
	const canaries = $derived(detail === null ? null : judgeCanaries(detail));
	const probability = $derived(judgeProbabilityEvidence(detail?.judge_probability_evidence));
</script>

<section class="digest-details" aria-labelledby="judge-digest-details" data-judge-digest={selected}>
	<h3 id="judge-digest-details">Selected digest details</h3>
	<p class="provenance">
		<time datetime={selected}>{longDate(selected)}</time> (UTC digest){#if identity},
			Council run {identity.run}, attempt {exact(identity.attempt)}{/if}.
	</p>
	{#if detail && canaries}
		<div class="selected-notes">
			<section aria-labelledby="judge-known-answers">
				<h4 id="judge-known-answers">Known-answer pairs</h4>
				{#if canaries.graded}
					<p><strong>{exact(canaries.matches)} of {exact(canaries.items.length)} expected pairs matched</strong> the saved agent-labelled key.</p>
					<p>Cohen's kappa:
						{#if canaries.kappa !== null && canaries.eligible !== null}
							{measuredText(canaries.kappa)} across {exact(canaries.eligible)} {canaries.eligible === 1 ? 'pair' : 'pairs'}.
						{:else if canaries.eligible !== null && canaries.eligible < canaries.items.length}
							Not measured: only {exact(canaries.eligible)} of {exact(canaries.items.length)} pairs agreed in both orders.
						{:else if canaries.eligible === canaries.items.length}
							Not measured: the chance-adjusted denominator was zero.
						{:else}
							Not recorded.
						{/if}
					</p>
				{:else}
					<p>Not recorded: this digest has no saved expected key. Observed answers are not graded.</p>
				{/if}
				{#if canaries.items.length > 0}
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
			<section aria-labelledby="judge-prior-fit">
				<h4 id="judge-prior-fit">Prior-fit calibration</h4>
				{#if detail.judge_probability_status === 'measured' && probability}
					<p>Probability Brier: <strong>{measuredText(detail.judge_probability_brier_score)}</strong>.
						Same-sample baseline Brier: {measuredText(detail.judge_probability_baseline_brier_score)}.
						Expected calibration error (ECE): {measuredText(detail.judge_probability_ece)} across {exact(probability.bins)} bins.</p>
					<p>{exact(probability.yes)} YES out of {exact(probability.pairs)} new agreed pairs in the fit's score range.
						The reference fit did not use these exact pairs.</p>
				{:else}
					<p>{judgeStatus(detail.judge_probability_status, PROBABILITY_STATUS)}</p>
				{/if}
				{#if probability}
					<p>Reference: {longDate(probability.date)} (digest), Council run {probability.run}.</p>
				{/if}
			</section>
		</div>
	{:else}
		<p>Judge record: {dayNote}</p>
	{/if}
</section>

<style>
	h3, h4, p { margin: 0; overflow-wrap: anywhere; }
	h3 {
		font-family: var(--font-display);
		font-size: var(--console-panel-title-size);
		line-height: var(--console-panel-title-leading);
		font-weight: var(--console-panel-title-weight);
		letter-spacing: var(--console-panel-title-tracking);
	}
	.digest-details {
		grid-column: 1 / -1;
		display: grid;
		gap: var(--space-2);
		padding-block-start: var(--console-panel-gap);
		border-block-start: 1px solid var(--color-rule);
	}
	.provenance {
		color: var(--color-text-secondary);
		font-size: var(--console-small-size);
		line-height: var(--console-small-leading);
	}
	.selected-notes {
		display: grid;
		align-items: start;
		gap: var(--console-panel-gap) var(--space-6);
		margin-block-start: var(--space-2);
	}
	.selected-notes section { display: grid; gap: var(--space-2); }
	@media (min-width: 1024px) { .selected-notes { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
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
