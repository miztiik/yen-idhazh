<script lang="ts">
	/** One role of the chart on the Data explorer's Chart tab: a pill that shows the role and the
	 * column it holds, and opens a floating list of the answer's columns the role can take.
	 *
	 * The list is the page's floating list (`floating-list.ts`): it closes on a press or a focus
	 * outside it, on Escape and after a pick in a one-column list, and gives focus back to its pill.
	 * It floats, so opening it moves nothing. Its lines are radio inputs, or checkboxes for a role
	 * that takes several columns, each with the column's type in its family's colour, in the
	 * answer's order; a filter at its head keeps the names holding the typed text anywhere. A role
	 * with no column it can take keeps its pill, quieter and with no chevron, opens nothing, and
	 * stays a Tab stop so a keyboard reader reaches it (`aria-disabled`, never `disabled`). The
	 * look and keys are Jony's and the words Susan's, both 2026-10-07.
	 */
	import { tick } from 'svelte';
	import Icon from '$lib/icons/Icon.svelte';
	import ColumnType from '$lib/console/explorer/ColumnType.svelte';
	import { closeAfterPick, closesWhenLeft } from '$lib/console/explorer/floating-list';
	import { AT_MOST_SENTENCE, pillFace, pillName, type ChartRole, type RoleOption } from '$lib/console/explorer/chart-roles';

	let {
		role,
		options,
		chosen,
		max,
		onChange
	}: {
		role: ChartRole;
		/** The columns the role can take, in the answer's order. Empty when it can take none. */
		options: readonly RoleOption[];
		/** The values the role holds, in the answer's order. */
		chosen: readonly string[];
		/** The most columns a several-column role holds. */
		max: number;
		onChange: (values: string[]) => void;
	} = $props();

	const group = $props.id();
	let details = $state<HTMLDetailsElement | null>(null);
	let list = $state<HTMLElement | null>(null);
	let filterField = $state<HTMLInputElement | null>(null);
	let typed = $state('');
	let current = $state<string | null>(null);
	/** The pointer that opened the list: a touch puts focus on the checked line, so a phone's
	 *  keyboard rises only when the reader taps the filter. */
	let opener = 'mouse';
	/** Set while Space is down on a line: Space checks a line and leaves the list open. */
	let spacePressed = false;

	const empty = $derived(options.length === 0);
	const face = $derived(pillFace(options, chosen));
	const label = $derived(pillName(role, options, chosen));
	const wanted = $derived(typed.trim().toLowerCase());
	const shown = $derived(wanted === '' ? options : options.filter((option) => option.name.toLowerCase().includes(wanted)));
	const full = $derived(role.several && chosen.length >= max);
	/** The one line Tab reaches in a list of checkboxes, so Tab leaves the list as it does a group of radios. */
	const stop = $derived(current !== null && shown.some((option) => option.value === current) ? current : (shown.find((option) => chosen.includes(option.value)) ?? shown[0])?.value ?? null);

	function lines(): HTMLInputElement[] {
		return [...(list?.querySelectorAll<HTMLInputElement>('input[data-line]') ?? [])];
	}

	/** The name broken after each `_`, so a long name wraps where it reads and is never cut. */
	function parts(name: string): string[] {
		return name.split(/(?<=_)/);
	}

	/** Hang the list under its pill, at least as wide as the pill's slot and at most as wide as the
	 *  role row's content box, moved back inside that box where it would pass its end, and no
	 *  taller than the room down to the window's bottom edge. */
	function place() {
		if (details === null || list === null) return;
		const pill = details.querySelector('summary')?.getBoundingClientRect();
		const row = details.closest<HTMLElement>('[data-chart-roles]');
		if (pill === undefined || row === null) return;
		const box = row.getBoundingClientRect();
		const style = getComputedStyle(row);
		const start = box.left + parseFloat(style.paddingLeft);
		const end = box.right - parseFloat(style.paddingRight);
		list.style.minInlineSize = `${pill.width}px`;
		list.style.maxInlineSize = `${end - start}px`;
		list.style.insetInlineStart = '0px';
		list.style.maxBlockSize = `calc(${document.documentElement.clientHeight - pill.bottom}px - var(--space-1) - var(--space-3))`;
		const width = list.getBoundingClientRect().width;
		list.style.insetInlineStart = `${Math.max(start, Math.min(pill.left, end - width)) - pill.left}px`;
	}

	async function opened() {
		if (details === null || !details.open) {
			typed = '';
			current = null;
			return;
		}
		await tick();
		if (opener === 'touch') (lines().find((line) => line.checked) ?? lines()[0] ?? filterField)?.focus();
		else filterField?.focus();
	}

	function press(event: MouseEvent) {
		if (empty) event.preventDefault();
	}

	function pillKey(event: KeyboardEvent) {
		if (event.key === 'Enter' || event.key === ' ') opener = 'keyboard';
		if (event.key !== 'ArrowDown' || empty || details === null || details.open) return;
		event.preventDefault();
		opener = 'keyboard';
		details.open = true;
	}

	function move(from: HTMLInputElement | null, step: number) {
		const all = lines();
		const at = from === null ? -1 : all.indexOf(from);
		const next = all[at + step];
		if (next !== undefined) {
			current = next.value;
			next.focus();
		} else if (at + step < 0) {
			filterField?.focus();
		}
	}

	function filterKey(event: KeyboardEvent) {
		if (event.key !== 'ArrowDown') return;
		event.preventDefault();
		move(null, 1);
	}

	function choose(value: string, checked: boolean): string[] {
		if (!role.several) return [value];
		const next = new Set(chosen);
		if (checked) next.add(value);
		else next.delete(value);
		return options.map((option) => option.value).filter((one) => next.has(one));
	}

	function lineKey(event: KeyboardEvent, option: RoleOption) {
		const line = event.currentTarget as HTMLInputElement;
		if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
			event.preventDefault();
			move(line, event.key === 'ArrowDown' ? 1 : -1);
		} else if (event.key === ' ') {
			spacePressed = true;
		} else if (event.key === 'Enter' && !role.several) {
			event.preventDefault();
			onChange([option.value]);
			void closeAfterPick(details);
		}
	}

	function linePress(event: MouseEvent, option: RoleOption) {
		const line = event.currentTarget as HTMLInputElement;
		const byKey = spacePressed || event.detail === 0;
		spacePressed = false;
		current = option.value;
		if (role.several && full && !chosen.includes(option.value)) {
			event.preventDefault();
			return;
		}
		onChange(choose(option.value, line.checked));
		if (!role.several && !byKey) void closeAfterPick(details);
	}

	/** Place the list in the task that opens it, before the page paints, so its first frame is its
	 *  only one. `toggle` arrives a task later, after a paint that would show the list at its own
	 *  width and then widen it under the reader's eye. */
	$effect(() => {
		if (details === null) return;
		const again = () => {
			if (details?.open) place();
		};
		const opening = new MutationObserver(again);
		opening.observe(details, { attributes: true, attributeFilter: ['open'] });
		addEventListener('resize', again);
		return () => {
			opening.disconnect();
			removeEventListener('resize', again);
		};
	});
</script>

<details class="column-picker" class:empty data-role={role.id} bind:this={details} use:closesWhenLeft ontoggle={opened}>
	<summary aria-label={label} aria-disabled={empty ? 'true' : undefined} onpointerdown={(event) => (opener = event.pointerType)} onclick={press} onkeydown={pillKey}>
		<span class="pill-role">{role.word}</span>
		<span class="pill-face"><span class="pill-name" data-pill-name>{face.name}</span>{#if face.more}<span class="pill-more">{face.more}</span>{/if}</span>
		{#if !empty}<span class="pill-mark"><Icon id="choice-list" /></span>{/if}
	</summary>
	<div class="pill-list" bind:this={list} data-pill-list>
		<label class="pill-filter">
			<span>Find a column</span>
			<input bind:this={filterField} bind:value={typed} type="search" autocomplete="off" spellcheck="false" onkeydown={filterKey} />
		</label>
		{#if shown.length === 0}
			<p class="pill-note">No column here has "{typed.trim()}" in its name.</p>
		{/if}
		<ul aria-label={role.word}>
			{#each shown as option (option.value)}
				<li>
					<label class="pill-line" data-column={option.value}>
						<input
							data-line
							type={role.several ? 'checkbox' : 'radio'}
							name={group}
							value={option.value}
							checked={chosen.includes(option.value)}
							tabindex={role.several ? (option.value === stop ? 0 : -1) : undefined}
							aria-disabled={full && !chosen.includes(option.value) ? 'true' : undefined}
							onkeydown={(event) => lineKey(event, option)}
							onclick={(event) => linePress(event, option)}
						/>
						<code class="pill-line-name">{#each parts(option.name) as part, index}{#if index > 0}<wbr />{/if}{part}{/each}</code>
						{#if option.type !== null}<ColumnType type={option.type} />{/if}
					</label>
				</li>
			{/each}
		</ul>
		{#if full}<p class="pill-note pill-foot">{AT_MOST_SENTENCE}</p>{/if}
	</div>
</details>

<style>
	.column-picker {
		position: relative;
		min-inline-size: 0;
		block-size: 100%;
	}

	summary {
		box-sizing: border-box;
		display: flex;
		align-items: center;
		gap: var(--space-2);
		block-size: var(--workbench-control);
		padding-inline: var(--space-2);
		overflow: hidden;
		border: 1px solid var(--color-rule-strong);
		border-radius: var(--radius-md);
		background: var(--color-surface);
		white-space: nowrap;
		list-style: none;
		cursor: pointer;
	}

	summary::-webkit-details-marker {
		display: none;
	}

	summary:focus-visible {
		outline: 2px solid var(--color-focus);
		outline-offset: 2px;
	}

	/* No column for this role: the word None, no chevron and a quieter edge, so a reader is told
	   three ways and colour is never the only one. */
	.empty > summary {
		border-color: var(--color-rule);
		cursor: default;
	}

	.pill-role {
		flex: none;
		color: var(--color-text-tertiary);
		font-size: var(--text-xs);
		font-weight: 600;
		letter-spacing: var(--tracking-label);
		text-transform: uppercase;
	}

	/* The name and the count after it read as one face, `summary_ms, 2 more`. Only the end of the
	   name gives way: the role word, the count and the chevron hold. */
	.pill-face {
		display: flex;
		flex: 0 1 auto;
		min-inline-size: 0;
		color: var(--color-text);
		font-family: var(--font-data);
		font-size: var(--text-xs);
	}

	.pill-name {
		flex: 0 1 auto;
		min-inline-size: 0;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.pill-more {
		flex: none;
	}

	.pill-mark {
		flex: none;
		display: inline-flex;
		margin-inline-start: auto;
		color: var(--color-text-secondary);
	}

	.pill-list {
		display: none;
	}

	.column-picker[open] .pill-list {
		position: absolute;
		z-index: 10;
		inset-block-start: calc(100% + var(--space-1));
		display: block;
		inline-size: max-content;
		overflow-y: auto;
		overscroll-behavior: contain;
		scrollbar-width: thin;
		scrollbar-color: var(--color-rule-strong) transparent;
		padding: var(--space-1);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-md);
		background: var(--color-surface-raised);
		box-shadow: var(--shadow-md);
	}

	/* The filter stays at the list's head while its lines scroll under it. */
	.pill-filter {
		position: sticky;
		inset-block-start: calc(-1 * var(--space-1));
		z-index: 1;
		display: flex;
		align-items: center;
		gap: var(--space-2);
		min-block-size: var(--workbench-control);
		padding-inline: var(--space-2);
		background: var(--color-surface-raised);
		color: var(--color-text-secondary);
		font-size: var(--text-xs);
	}

	.pill-filter input {
		flex: 1 1 auto;
		min-inline-size: 0;
		min-block-size: calc(var(--workbench-control) - 2 * var(--space-1));
		padding-inline: var(--space-2);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-md);
		background: var(--color-bg);
		color: var(--color-text);
		font-size: var(--workbench-field-text);
	}

	ul {
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.pill-line {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		min-block-size: var(--workbench-control);
		padding-inline: var(--space-2);
		border-radius: var(--radius-sm);
		cursor: pointer;
	}

	.pill-line:hover,
	.pill-line:focus-within {
		background: var(--tint-neutral);
	}

	.pill-line input {
		flex: none;
		margin: 0;
	}

	.pill-line input[aria-disabled='true'] {
		cursor: default;
	}

	.pill-line-name {
		min-inline-size: 0;
		padding-inline-start: 2ch;
		text-indent: -2ch;
		overflow-wrap: anywhere;
		color: var(--color-text);
		font-family: var(--font-data);
		font-size: var(--text-xs);
	}

	.pill-line > :global(.column-type) {
		margin-inline-start: auto;
	}

	.pill-note {
		margin: 0;
		padding: var(--space-1) var(--space-2);
		color: var(--color-text-secondary);
		font-size: var(--text-xs);
	}
</style>
