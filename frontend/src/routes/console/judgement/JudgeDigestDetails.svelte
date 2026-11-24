<script lang="ts">
	import type { CanaryReading } from '$lib/console/judge-canaries';
	import {
		judgeNumber, judgeProbabilityEvidence, judgeStatus, PROBABILITY_STATUS, type JudgeIdentity
	} from '$lib/console/judge-observations';
	import type { Row } from '$lib/data/ledger';
	import { longDate } from '$lib/format';
	import { numberFormatter } from '$lib/number-format';
	import type { ChartConfig } from '$lib/server/config';
	import JudgeCanaryDetails from './JudgeCanaryDetails.svelte';

	let { selected, identity, detail, dayNote, chart, canaries }: {
		selected: string;
		identity: JudgeIdentity | null;
		detail: Row | null;
		dayNote: string;
		chart: ChartConfig;
		canaries: CanaryReading | null;
	} = $props();

	const number = $derived(numberFormatter(chart.number_format));
	const exact = (value: number) => number(value, { exact: true });
	const measuredText = (value: unknown) => {
		const n = judgeNumber(value);
		return n === null ? 'Not recorded' : number(n, { si: false });
	};
	const probability = $derived(judgeProbabilityEvidence(detail?.judge_probability_evidence));
</script>

<section class="digest-details" aria-labelledby="judge-digest-details" data-judge-digest={selected}>
	<h3 id="judge-digest-details">Selected digest details</h3>
	<p class="provenance">
		<time datetime={selected}>{longDate(selected)}</time> (UTC digest){#if identity},
			Council run {identity.run}, attempt {exact(identity.attempt)}{/if}.
	</p>
	{#if detail}
		<div class="selected-notes">
			{#if canaries}<JudgeCanaryDetails reading={canaries} format={chart.number_format} />{/if}
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
</style>
