<script lang="ts">
	/** The console shell: the title, the strip and the verdict band, drawn once.
	 *
	 * The band is the answer to "is the pipeline working", and it is the first
	 * thing the console asks for - `+layout.ts` beside this file fetches
	 * `console/band.json` and nothing else waits behind it. Drawing it here is
	 * the other half of that: one band above three route panels, so a move
	 * between routes never redraws the verdict and the three panels can never
	 * disagree about which of them is worst.
	 *
	 * The order is title, strip, band, control, content, and it is held by an
	 * oracle in `console-band.spec.ts`. Chrome above content is the one ordering
	 * a reader never has to learn, and the band's worst fact links down into the
	 * strip. The control stays on the route because it governs that route's
	 * panels and nothing above them.
	 *
	 * Each route renders the rest inside this section, so `[data-surface]`
	 * still holds the whole operator surface.
	 */
	import { page } from '$app/state';
	import ConsoleBand from '$lib/components/ConsoleBand.svelte';
	import ConsoleNav from '$lib/components/ConsoleNav.svelte';

	let { data, children } = $props();

	// Read off the route rather than passed in by each page. Three pages naming
	// their own id is three places for it to be wrong, and the routes already
	// carry the address they answer at.
	const active = $derived(
		data.routes.find((route) => route.href.replace(/\/$/, '') === page.route.id)?.id ?? 'pipelines'
	);
</script>

<section class="py-6" data-surface="operator" data-console-route={active}>
	<h1 class="text-[1.375rem] font-semibold tracking-[-0.011em] text-text">Console</h1>

	<ConsoleNav routes={data.routes} {active} />
	<ConsoleBand band={data.band} />

	<!-- Said once, above every panel, and only to a reader with no script.
	     The band above is real markup and stays readable; the panels below draw
	     rows a browser fetches, so with no script they keep their reserved shape
	     and stay empty. A page that let those boxes sit there unexplained would
	     be a page claiming the pipeline recorded nothing. -->
	<noscript>
		<p class="console-noscript" data-console-noscript>
			The verdict above is in this page. Everything below it is drawn from
			month files a browser fetches, so with JavaScript off the panels keep
			their shape and stay empty.
		</p>
	</noscript>

	{@render children()}
</section>

<style>
	.console-noscript {
		margin-top: var(--space-4);
		padding: var(--space-3) var(--space-4);
		border: 1px solid var(--color-rule);
		border-radius: var(--radius-md);
		background: var(--tint-neutral);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}
</style>
