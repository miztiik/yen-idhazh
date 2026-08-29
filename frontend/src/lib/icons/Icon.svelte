<script lang="ts">
	/** One glyph, one id, one tint.
	 *
	 * Colour arrives by semantic tint rather than by multi-colour artwork: the
	 * glyph is monochrome and inherits `currentColor`, so the thing it sits in
	 * decides the hue. One set, and a new status arrives with a slot already
	 * waiting instead of a second artwork file.
	 *
	 * A component names an icon and never holds a `<path>`; `icons.spec.ts`
	 * asserts that in both directions.
	 */
	import { ICONS, type IconId } from './generated';

	let {
		id,
		size = 16,
		label,
		class: className = ''
	}: {
		id: IconId;
		size?: number;
		/** Give this only where the icon is the whole meaning. Beside text that
		 * already says it, an icon is decoration and gets hidden instead. */
		label?: string;
		class?: string;
	} = $props();
</script>

<svg
	class="icon {className}"
	width={size}
	height={size}
	viewBox="0 0 24 24"
	fill="none"
	stroke="currentColor"
	stroke-width="2"
	stroke-linecap="round"
	stroke-linejoin="round"
	role={label ? 'img' : 'presentation'}
	aria-label={label}
	aria-hidden={label ? undefined : 'true'}
	focusable="false"
>
	<!-- eslint-disable-next-line svelte/no-at-html-tags -->
	{@html ICONS[id]}
</svg>

<style>
	.icon {
		display: inline-block;
		flex: none;
		vertical-align: -0.125em;
	}
</style>
