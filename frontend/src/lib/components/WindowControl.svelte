<script lang="ts">
	/** Choose the shared console window from the configured radio presets.
	 * Null leaves every tile unchecked for a custom span. The visible D suffix
	 * is expanded in each accessible name; WindowStatus holds reach and fetch
	 * costs so changing that text cannot resize a control.
	 */
	import { plural } from '$lib/format';
	import ChoiceTiles from './ChoiceTiles.svelte';

	let {
		days,
		presets,
		busy = false,
		ready = false,
		statusId = 'window-control-status',
		compact = false,
		onChange
	}: {
		days: number | null;
		presets: readonly number[];
		busy?: boolean;
		/** False until a browser has run. The control does nothing before that,
		 * so it says so instead of accepting a click it cannot honour. */
		ready?: boolean;
		statusId?: string | null;
		/** Use a native select on narrow console title bands. */
		compact?: boolean;
		onChange: (days: number) => void;
	} = $props();

	const items = $derived(
		presets.map((preset) => ({
			value: preset,
			shown: `${preset}D`,
			spoken: plural(preset, 'day', 'days')
		}))
	);
</script>

<fieldset
	class="window-control"
	data-window-control
	data-window-compact={compact ? 'true' : undefined}
	data-window-days={days ?? undefined}
	data-window-busy={busy ? 'true' : 'false'}
	aria-busy={busy}
	aria-describedby={statusId ?? undefined}
>
	<legend class="sr-only">Days shown</legend>
	<div class="window-presets"><ChoiceTiles
		name="console-window"
		{items}
		selected={days}
		disabled={!ready}
		tileAttribute="data-window-preset"
		{onChange}
	/></div>
	{#if compact}
		<select class="window-native" aria-label="Days shown" disabled={!ready} value={days ?? ''}
			onchange={(event) => onChange(Number(event.currentTarget.value))} data-window-select>
			{#if days === null}<option value="" disabled>Custom span</option>{/if}
			{#each presets as preset}<option value={preset}>{plural(preset, 'day', 'days')}</option>{/each}
		</select>
	{/if}
</fieldset>

<style>
	.window-control {
		min-inline-size: 0;
		margin: 0;
		padding: 0;
		border: 0;
	}
	.window-native {
		display: none;
		min-block-size: var(--console-control-min-height);
		padding-inline: var(--console-control-gap);
		border: 1px solid var(--color-rule-strong);
		background: var(--color-surface);
		color: var(--color-text);
	}
	@media (max-width: 639px) {
		[data-window-compact='true'] .window-presets { display: none; }
		.window-native { display: block; }
	}
</style>