<script lang="ts">
	/** Two themes, one button, and the glyph never flips.
	 *
	 * The page is the state indicator - a reader can see which theme they are
	 * in - so an icon that changed with the theme would be a second and weaker
	 * copy of that. The moon names the control; the label names the action.
	 * There is no `aria-pressed` for the same reason: this is a switch between
	 * two states, not a thing that is on or off.
	 */
	import { apply, storedChoice, syncBrowserChrome } from '$lib/theme';
	import type { ThemeChoice } from '$lib/theme';
	import Icon from '$lib/icons/Icon.svelte';
	import { onMount } from 'svelte';

	// Dark until the stored choice is read, which matches what the document is
	// already painting.
	let choice = $state<ThemeChoice>('dark');

	onMount(() => {
		choice = storedChoice();
		// The tag in app.html holds the base theme, so a reader who stored light
		// would otherwise sit under dark chrome until they touched the control.
		syncBrowserChrome();
	});

	function toggle() {
		choice = choice === 'dark' ? 'light' : 'dark';
		apply(choice);
	}
</script>

<button
	type="button"
	onclick={toggle}
	class="inline-flex min-h-11 min-w-11 items-center justify-center rounded-full border border-rule text-text-tertiary transition-colors hover:text-accent"
	aria-label={choice === 'dark' ? 'Switch to the light theme' : 'Switch to the dark theme'}
	data-theme-toggle
>
	<Icon id="theme-dark" />
	<span class="theme-word">{choice === 'dark' ? 'Light theme' : 'Dark theme'}</span>
</button>

<style>
	.theme-word { display: none; }
	:global(.frame:has([data-surface='operator'])) button {
		gap: var(--console-control-gap);
		min-block-size: var(--console-control-min-height);
		padding: var(--console-control-padding-block) var(--console-control-padding-inline);
		border-radius: var(--console-control-radius);
		background: var(--color-surface);
		color: var(--color-text-secondary);
		font-size: var(--console-control-size);
		line-height: var(--console-control-leading);
		font-weight: var(--console-control-weight);
	}
	:global(.frame:has([data-surface='operator'])) .theme-word { display: inline; }
</style>
