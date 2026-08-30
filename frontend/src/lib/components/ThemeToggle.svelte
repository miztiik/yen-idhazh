<script lang="ts">
	import { apply, storedChoice, watchSystem } from '$lib/theme';
	import type { ThemeChoice } from '$lib/theme';
	import Icon from '$lib/icons/Icon.svelte';
	import type { IconId } from '$lib/icons/generated';
	import { onMount } from 'svelte';

	let choice = $state<ThemeChoice>('system');
	// Auto gets no mark on purpose: it means "whatever the system says", and a sun
	// or a moon beside it would be a claim about which one that is.
	const OPTIONS: { value: ThemeChoice; label: string; icon: IconId | null }[] = [
		{ value: 'system', label: 'Auto', icon: null },
		{ value: 'light', label: 'Light', icon: 'theme-light' },
		{ value: 'dark', label: 'Dark', icon: 'theme-dark' }
	];

	onMount(() => {
		choice = storedChoice();
		return watchSystem(() => {
			if (choice === 'system') apply('system');
		});
	});

	function pick(value: ThemeChoice) {
		choice = value;
		apply(value);
	}
</script>

<div
	class="inline-flex items-center rounded-full border border-rule p-0.5"
	role="group"
	aria-label="Theme"
>
	{#each OPTIONS as option (option.value)}
		<button
			type="button"
			onclick={() => pick(option.value)}
			aria-pressed={choice === option.value}
			class="min-h-11 rounded-full px-3 text-[0.8125rem] transition-colors"
			class:text-accent={choice === option.value}
			class:text-text-tertiary={choice !== option.value}
		>
			{option.label}
		</button>
	{/each}
</div>
