<script lang="ts">
	/** The price this page multiplies tokens by, and where that price came from.
	 *
	 * **The figure it feeds is a counterfactual and never a bill.** Nothing bills
	 * us: Actions minutes are free on a public repository, which is exactly why
	 * the wall clock alone cannot say whether four hours of runner time was a
	 * good trade. Priced at somebody else's rate the same run gets a second unit,
	 * and that is the one question no other panel on this site answers. CLAUDE.md
	 * Rule #10 carries the owner's carve-out for it on one condition, which is
	 * this control: a money figure whose basis is invisible is the exact thing
	 * that rule exists to prevent, so the rate and its source are printed beside
	 * every cost on the page.
	 *
	 * The configured pair comes from `config/idhazh.json` (Rule #6). A rate the
	 * operator types is kept in `localStorage` and read on mount and never during
	 * prerender, so the first paint always matches the prerendered document and
	 * the page never flickers from one number to another before a script runs.
	 * With no script at all the inputs stay disabled and the page prices every
	 * run at the configured rate, which is a complete answer rather than a
	 * broken control.
	 */
	import { money, type CostRate } from '$lib/charts/machine';
	import { onMount } from 'svelte';

	let {
		configured,
		inputRate = $bindable(),
		outputRate = $bindable(),
		source = $bindable()
	}: {
		/** The committed pair. What `Use the configured rate` returns to. */
		configured: CostRate;
		/** Currency per million prompt tokens. */
		inputRate: number;
		/** Currency per million written tokens. */
		outputRate: number;
		/** Which of the two the page is pricing with, right now. */
		source: 'configured' | 'yours';
	} = $props();

	const KEY = 'idhazh:cost-rate';

	let mounted = $state(false);

	function remember(input: number, output: number): void {
		try {
			localStorage.setItem(KEY, JSON.stringify({ input, output }));
		} catch {
			// A browser that refuses storage still gets a working control for this
			// visit. Losing the rate on reload is a smaller failure than a page
			// that throws while drawing a number.
		}
	}

	onMount(() => {
		mounted = true;
		let stored: unknown = null;
		try {
			const raw = localStorage.getItem(KEY);
			stored = raw === null ? null : JSON.parse(raw);
		} catch {
			stored = null;
		}
		if (stored === null || typeof stored !== 'object') return;
		const pair = stored as { input?: unknown; output?: unknown };
		const input = Number(pair.input);
		const output = Number(pair.output);
		if (!Number.isFinite(input) || !Number.isFinite(output) || input < 0 || output < 0) return;
		inputRate = input;
		outputRate = output;
		source = 'yours';
	});

	function change(which: 'input' | 'output', event: Event): void {
		const value = Number((event.currentTarget as HTMLInputElement).value);
		if (!Number.isFinite(value) || value < 0) return;
		if (which === 'input') inputRate = value;
		else outputRate = value;
		source = 'yours';
		remember(inputRate, outputRate);
	}

	function reset(): void {
		inputRate = configured.inputPerMillion;
		outputRate = configured.outputPerMillion;
		source = 'configured';
		try {
			localStorage.removeItem(KEY);
		} catch {
			// See remember().
		}
	}
</script>

<div class="rate" data-rate-control data-rate-source={source}>
	<div class="fields">
		<label class="field">
			<span class="field-label">Prompt tokens</span>
			<span class="field-row">
				<input
					type="number"
					min="0"
					step="0.01"
					inputmode="decimal"
					disabled={!mounted}
					value={inputRate}
					data-rate-input="input"
					aria-label="Price per million prompt tokens, in {configured.currency}"
					onchange={(event) => change('input', event)}
				/>
				<span class="per">{configured.currency} a million</span>
			</span>
		</label>

		<label class="field">
			<span class="field-label">Written tokens</span>
			<span class="field-row">
				<input
					type="number"
					min="0"
					step="0.01"
					inputmode="decimal"
					disabled={!mounted}
					value={outputRate}
					data-rate-input="output"
					aria-label="Price per million written tokens, in {configured.currency}"
					onchange={(event) => change('output', event)}
				/>
				<span class="per">{configured.currency} a million</span>
			</span>
		</label>
	</div>

	<!-- The whole point of the control. A figure in currency reads as a fact
	     about a bank account unless the sentence beside it says whose price it
	     is and that nobody sent it. -->
	<p class="basis" data-rate-basis>
		{source === 'yours' ? 'Using your rate' : 'Using the configured rate'}:
		<strong>{money(inputRate, configured.currency, 4)}</strong> a million prompt tokens and
		<strong>{money(outputRate, configured.currency, 4)}</strong> a million written tokens.
		{#if source === 'yours'}
			The configured pair is {money(configured.inputPerMillion, configured.currency, 4)} and
			{money(configured.outputPerMillion, configured.currency, 4)}.
			<button type="button" class="reset" data-rate-reset onclick={reset}>
				Use the configured rate
			</button>
		{:else}
			It is in <code>config/idhazh.json</code> under <code>observability</code>, and it is a
			starting point somebody has to set rather than a price anybody quoted us.
		{/if}
	</p>

	{#if !mounted}
		<p class="basis" data-rate-static>
			Typing a different rate needs a script. Without one the page prices every run at the
			configured pair, which is what these charts are drawn from.
		</p>
	{/if}
</div>

<style>
	.rate {
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
	}

	.fields {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-4);
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
	}

	.field-label {
		font-size: var(--text-xs);
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--color-text-tertiary);
	}

	.field-row {
		display: flex;
		align-items: baseline;
		gap: var(--space-2);
	}

	input {
		inline-size: 7rem;
		padding: var(--space-1) var(--space-2);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-sm);
		background: var(--color-surface);
		color: var(--color-text);
		font: inherit;
		font-variant-numeric: tabular-nums;
	}

	input:disabled {
		color: var(--color-text-tertiary);
	}

	.per {
		font-size: var(--text-sm);
		color: var(--color-text-tertiary);
	}

	.basis {
		margin: 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.reset {
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-sm);
		padding: 2px var(--space-2);
		background: var(--color-surface);
		color: var(--color-accent);
		font: inherit;
		font-size: var(--text-sm);
		cursor: pointer;
	}
</style>
