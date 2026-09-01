<script lang="ts">
	/** The three facts that stand on every console route, under the strip.
	 *
	 * Three and no more. A band that grows becomes a fourth page nobody chose to
	 * open, and the point of it is that an operator who lands anywhere already
	 * knows whether yesterday worked, what is worst, and how much room is left.
	 *
	 * The window control was a fourth member until 2026-08-31 and is not one now.
	 * The band is deliberately not windowed, so a control inside it sat in a panel
	 * it does not govern. It stands on its own below the band.
	 *
	 * None of the three is windowed - the band stands on every route, so a figure
	 * that moved when a control on one route moved would read as three different
	 * sites.
	 */
	import { base } from '$app/paths';
	import { PAGES_CAP_BYTES } from '$lib/charts/glance';
	import type { ConsoleBandFacts, Health } from '$lib/server/console-shell';

	let { band }: { band: ConsoleBandFacts } = $props();

	const capPct = $derived(band.size.capFraction === null ? null : band.size.capFraction * 100);

	/** The fill ramp, not the band ramp: the band tokens are text colours and a
	 * 10px solid is not text. These are the three fills the run strip 800px down
	 * the Pipelines route paints a run in, so the row is a system rather than a
	 * mark invented for one panel. */
	const FILL: Record<Health, string> = {
		green: 'var(--fill-high)',
		amber: 'var(--fill-medium)',
		red: 'var(--fill-low)'
	};
</script>

<section class="band" aria-label="Yesterday, the worst thing and site size" data-console-band>
	<div class="facts">
		<div class="fact" data-band-fact="verdict">
			<!-- A label, not a heading. Three headings of band chrome above the page's
			     own would put the furniture at the top of the outline on all three
			     routes; the section names itself instead. -->
			<p class="fact-label">Yesterday</p>
			<p class="fact-body" data-band-verdict data-band-health={band.verdict.health}>
				{band.verdict.sentence}
			</p>
			{#if band.verdict.runs.length > 0}
				<!-- One square a run, in the order they ran. It says what the sentence
				     cannot: whether one run ate every failure or all five limped. Every
				     square names its verdict in words, so the colour is never the only
				     signal. -->
				<p class="runs" data-band-runs={band.verdict.runs.length}>
					{#each band.verdict.runs as run, index (index)}
						<span
							class="run"
							role="img"
							style="background: {FILL[run.health]}"
							title={run.label}
							aria-label={run.label}
							data-band-run={run.health}
						></span>
					{/each}
					{#if band.verdict.moreRuns > 0}
						<span class="runs-more" data-band-runs-more={band.verdict.moreRuns}
							>+{band.verdict.moreRuns}</span
						>
					{/if}
				</p>
			{/if}
		</div>

		<div class="fact" data-band-fact="worst">
			<p class="fact-label">Worst thing right now</p>
			{#if band.worst}
				<!-- What the state costs, not only what it is. The strip keeps the short
				     fragment; the band printing the same two words was one fact told
				     twice, 337px apart on a phone. -->
				<p class="fact-body" data-band-worst data-band-worst-route={band.worst.id}>
					{band.worst.sentence} On
					<a class="fact-link" href="{base}{band.worst.href}">{band.worst.label}</a>.
				</p>
			{:else}
				<p class="fact-body" data-band-worst="clear">
					Nothing on any of the three routes is asking for attention.
				</p>
			{/if}
		</div>

		<div class="fact" data-band-fact="size">
			<p class="fact-label">Site size</p>
			{#if capPct !== null}
				<!-- Drawn as markup, so it is on the page before any script runs. The
				     number is beside it because a 0.1 percent bar is invisible and a
				     bar nobody can read is not a measurement. -->
				<div
					class="track"
					role="img"
					aria-label="{capPct.toFixed(1)} percent of the 1 GB limit"
					data-band-size-pct={capPct.toFixed(2)}
					data-band-size-cap={PAGES_CAP_BYTES}
				>
					<span class="fill" style="inline-size: {Math.max(capPct, 0.4).toFixed(2)}%"></span>
				</div>
			{/if}
			<p class="fact-body" data-band-size>{band.size.sentence}</p>
		</div>
	</div>
</section>

<style>
	/* One raised surface carrying all three. Three separate cards would read as
	   three panels the page owns, and the band belongs to the console rather
	   than to the route under it. */
	.band {
		margin-top: var(--space-4);
		padding: var(--space-4);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-lg);
		background: var(--color-surface-raised);
		box-shadow: var(--shadow-sm);
	}

	.facts {
		display: grid;
		gap: var(--space-4);
		grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
	}

	.fact {
		min-inline-size: 0;
	}

	.fact-label {
		margin: 0;
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		font-weight: 400;
		color: var(--color-text-tertiary);
	}

	.fact-body {
		margin: var(--space-1) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text);
	}

	.fact-link {
		color: var(--color-accent);
	}

	.fact-link:hover {
		text-decoration: underline;
	}

	.runs {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 3px;
		margin: var(--space-2) 0 0;
	}

	.run {
		display: block;
		inline-size: 10px;
		block-size: 10px;
		border-radius: var(--radius-sm);
	}

	.runs-more {
		margin-inline-start: var(--space-1);
		font-size: var(--text-xs);
		line-height: 1;
		color: var(--color-text-tertiary);
	}

	.track {
		block-size: 6px;
		margin-block: var(--space-2) var(--space-1);
		border-radius: var(--radius-full);
		background: var(--color-surface-sunken);
		overflow: hidden;
	}

	/* The categorical ramp. How full the site is has no agreed threshold at this
	   end of it, and a health colour here would publish one. */
	.fill {
		display: block;
		block-size: 100%;
		background: var(--chart-3);
	}
</style>
