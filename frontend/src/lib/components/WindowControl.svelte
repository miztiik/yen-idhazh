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
		onChange
	}: {
		days: number | null;
		presets: readonly number[];
		busy?: boolean;
		/** False until a browser has run. The control does nothing before that,
		 * so it says so instead of accepting a click it cannot honour. */
		ready?: boolean;
		statusId?: string | null;
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
	data-window-days={days ?? undefined}
	data-window-busy={busy ? 'true' : 'false'}
	aria-busy={busy}
	aria-describedby={statusId ?? undefined}
>
	<legend class="sr-only">Days shown</legend>
	<ChoiceTiles
		name="console-window"
		{items}
		selected={days}
		disabled={!ready}
		tileAttribute="data-window-preset"
		{onChange}
	/>
</fieldset>

<style>
	.window-control {
		min-inline-size: 0;
		margin: 0;
		padding: 0;
		border: 0;
	}
</style>