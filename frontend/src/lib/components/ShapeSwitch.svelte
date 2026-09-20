<script lang="ts" generics="T extends string">
	/** Two or three named states of one panel, for data that already draws them all.
	 *
	 * One control for the panel, never one per series and never a preference
	 * that follows the reader across the site. The default pair answers two
	 * questions off one array: stacked says what the mix is and how big the
	 * total got, lines say what each series did on its own. A stack hides a
	 * series that halved while its neighbour doubled; lines hide the total.
	 *
	 * **It ships only where no re-shaping is needed.** The values handed to the
	 * engine are the same list in every state - see `StackShape` in
	 * `$lib/charts/stacked` - and a panel that would need its data massaged to
	 * fit a second state gets no switch at all. A grain switch qualifies on the
	 * same terms: one builder call returns every grain it offers.
	 *
	 * Radio inputs, not a button that toggles: two named states a reader can see
	 * both of beats one state and a verb. It is the same shape `WindowControl`
	 * uses, and it needs no script to be readable - only to act.
	 */

	/** Stacked against lines, which is what every call site wanted until a panel
	 * needed a grain switch. Cast because a default cannot be written in the
	 * caller's own type; a caller with other states passes `options`. */
	const SHAPES = [
		{ value: 'bars', text: 'Stacked' },
		{ value: 'lines', text: 'Lines' }
	] as { value: T; text: string }[];

	let {
		shape = $bindable(),
		name,
		label = 'Shape',
		options = SHAPES
	}: {
		shape: T;
		/** Unique per panel: two radio groups sharing a name are one group. */
		name: string;
		label?: string;
		options?: { value: T; text: string }[];
	} = $props();
</script>

<fieldset class="switch" data-shape-switch={name} data-shape={shape}>
	<legend class="sr-only">{label}</legend>
	{#each options as option (option.value)}
		<label class="segment" data-shape-option={option.value}>
			<input type="radio" name="shape-{name}" value={option.value} bind:group={shape} />
			<span>{option.text}</span>
		</label>
	{/each}
</fieldset>

<style>
	.switch {
		display: inline-flex;
		gap: var(--space-1);
		margin: var(--space-3) 0 0;
		padding: 2px;
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-full);
	}

	.segment {
		display: inline-flex;
		align-items: center;
		min-block-size: 32px;
		padding-inline: var(--space-3);
		border-radius: var(--radius-full);
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		color: var(--color-text-secondary);
		cursor: pointer;
	}

	/* The input is the control and it keeps its own focus ring; only its box is
	   hidden, so a keyboard reaches the switch exactly as a pointer does. */
	.segment input {
		position: absolute;
		inline-size: 1px;
		block-size: 1px;
		margin: -1px;
		padding: 0;
		overflow: hidden;
		clip-path: inset(50%);
		white-space: nowrap;
	}

	.segment:has(input:checked) {
		background: var(--color-surface-sunken);
		color: var(--color-text);
	}

	.segment:has(input:focus-visible) {
		outline: 2px solid var(--color-focus);
		outline-offset: 2px;
	}
</style>
