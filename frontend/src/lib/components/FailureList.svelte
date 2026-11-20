<script lang="ts">
	/** Rank recorded failed rules at an explicitly selected stage, without item identities. */
	import FailureRuleRanking from './FailureRuleRanking.svelte';
	import type { FailureRuleRow } from '$lib/console/failure-rules';
	import type { TimeWindow } from '$lib/charts/viewport';

	let {
		window,
		max,
		readoutMaxShare,
		stages,
		ranking
	}: {
		ranking: readonly FailureRuleRow[];
		stages: { options: readonly string[]; chosen: string };
		window: TimeWindow;
		max: number;
		readoutMaxShare: number;
	} = $props();

	let chosenStage = $state<string | null>(null);
	const stageName = $props.id();
	const stage = $derived.by(() => {
		const picked = chosenStage !== null && stages.options.includes(chosenStage)
			? chosenStage : stages.chosen;
		if (stages.options.length === 0 || new Set(stages.options).size !== stages.options.length ||
			!stages.options.includes(picked)) {
			throw new Error('An identity-free failure ranking needs distinct stages and a chosen stage in that list.');
		}
		return picked;
	});
</script>

<section class="mt-8">
	<h3>Failure rule ranking</h3>
	{#if stages.options.length > 1}
		<fieldset data-failure-stages>
			<legend>Show rules for stage</legend>
			<div class="stage-choices">
				{#each stages.options as option (option)}
					<label><input type="radio" name={stageName} value={option} checked={stage === option}
						onchange={() => chosenStage = option} />{option}</label>
				{/each}
			</div>
		</fieldset>
	{/if}
	<FailureRuleRanking rows={ranking} {window} {stage} {max} {readoutMaxShare} />
</section>

<style>
	h3 { margin: 0; font-size: var(--console-panel-title-size); font-weight: var(--console-panel-title-weight); }
	fieldset { min-inline-size: 0; margin: var(--space-2) 0; padding: 0; border: 0; }
	legend { color: var(--color-text-secondary); font-size: var(--text-sm); }
	.stage-choices { display: flex; flex-wrap: wrap; gap: var(--space-1); }
	label {
		display: inline-flex; align-items: center; gap: var(--space-2);
		min-block-size: var(--console-control-min-height); padding-inline: var(--console-control-padding-inline);
		border-radius: var(--radius-sm); text-transform: capitalize; cursor: pointer;
	}
	label:has(input:checked) { background: var(--color-surface-sunken); font-weight: 600; }
	input { accent-color: var(--color-accent); }
</style>
