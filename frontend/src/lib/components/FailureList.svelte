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
	<fieldset class="stage-choices" data-failure-stages>
		<legend>Stage</legend>
		{#each stages.options as option (option)}
			<label><input type="radio" name={stageName} value={option} checked={stage === option}
				onchange={() => chosenStage = option} />{option}</label>
		{/each}
	</fieldset>
	<FailureRuleRanking rows={ranking} {window} {stage} {max} {readoutMaxShare} />
</section>
