<script lang="ts">
	/** The four facts that stand on every console route, above the strip.
	 *
	 * Four and no more. A band that grows becomes a fourth page nobody chose to
	 * open, and the point of it is that an operator who lands anywhere already
	 * knows whether yesterday worked, what is worst, and how much room is left.
	 *
	 * The first three are identical on all three routes and are not windowed -
	 * the band stands on every route, so a figure that moved when a control on
	 * one route moved would read as three different sites. The fourth is the
	 * window control itself, handed in by the route, because a control below the
	 * thing it governs is read second.
	 */
	import { base } from '$app/paths';
	import { PAGES_CAP_BYTES } from '$lib/charts/glance';
	import type { ConsoleBandFacts } from '$lib/server/console-shell';
	import type { Snippet } from 'svelte';

	let { band, window: windowSlot }: { band: ConsoleBandFacts; window: Snippet } = $props();

	const capPct = $derived(band.size.capFraction === null ? null : band.size.capFraction * 100);
</script>

<section class="band" aria-label="Yesterday, the worst thing, site size and the window" data-console-band>
	<div class="facts">
		<div class="fact" data-band-fact="verdict">
			<!-- A label, not a heading. Three headings of band chrome above the page's
			     own would put the furniture at the top of the outline on all three
			     routes; the section names itself instead. -->
			<p class="fact-label">Yesterday</p>
			<p class="fact-body" data-band-verdict data-band-health={band.verdict.health}>
				{band.verdict.sentence}
			</p>
		</div>

		<div class="fact" data-band-fact="worst">
			<p class="fact-label">Worst thing right now</p>
			{#if band.worst}
				<p class="fact-body" data-band-worst data-band-worst-route={band.worst.id}>
					{band.worst.text} &mdash; on
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
					aria-label="{capPct.toFixed(1)} percent of the 1 GB Pages cap"
					data-band-size-pct={capPct.toFixed(2)}
					data-band-size-cap={PAGES_CAP_BYTES}
				>
					<span class="fill" style="inline-size: {Math.max(capPct, 0.4).toFixed(2)}%"></span>
				</div>
			{/if}
			<p class="fact-body" data-band-size>{band.size.sentence}</p>
		</div>
	</div>

	<div class="window" data-band-window-slot>
		{@render windowSlot()}
	</div>
</section>

<style>
	/* One raised surface carrying all four. Three separate cards would read as
	   three panels the page owns, and the band belongs to the console rather
	   than to the route under it. */
	.band {
		margin-top: var(--space-5);
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
