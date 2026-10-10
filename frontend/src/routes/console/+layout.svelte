<script lang="ts">
	/** The console shell: the title, the strip, the sentence that dates the
	 * record, and the verdict band, drawn once above every route.
	 *
	 * The band is the answer to "is the pipeline working", and it is the first
	 * thing the console asks for - `+layout.ts` beside this file fetches
	 * `console/band.json` and nothing else waits behind it. Drawing it here is
	 * the other half of that: one band above every route's panels, so a move
	 * between routes never redraws the verdict and no two routes can disagree
	 * about which of them is worst.
	 *
	 * The order is title, strip, the completeness sentence, band, the days
	 * sentence, the route's jump links, content - held by an oracle in
	 * `console-band.spec.ts`. Chrome above content is the one ordering a reader
	 * never has to learn, and the band's worst fact links into the strip.
	 *
	 * **The strip is the tabs and the days control, one row from
	 * `frame.breakpoints_px[1]` up, and stuck to the top of the screen there**,
	 * so a reader nine panels down still has the span and every route in reach.
	 * `strip.ts` is what keeps the page still when it sticks. The control is drawn
	 * here and held by the route: it governs that route's panels and nothing above
	 * them, so the window stays in the route - its span, its fetches, its price
	 * per preset - and the route hands it up through `window-slot.ts`. Until it
	 * has, the control holds the configured window.
	 *
	 * **The completeness sentence is what tells a stopped pipeline from a quiet
	 * one.** Every chart draws the newest days that exist, so a chart whose data
	 * stopped looks as full as it did the day before; the sentence dates the
	 * record and, once a browser's clock is in hand, counts the days missing.
	 *
	 * Each route renders the rest inside this section, so `[data-surface]`
	 * still holds the whole operator surface.
	 */
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import ConsoleBand from '$lib/components/ConsoleBand.svelte';
	import ConsoleNav from '$lib/components/ConsoleNav.svelte';
	import WindowControl from '$lib/components/WindowControl.svelte';
	import WindowStatus from '$lib/components/WindowStatus.svelte';
	import { stripRoutes } from '$lib/console/band';
	import { consoleChromeOf } from '$lib/console/chrome';
	import { consoleKnobs, routeConsole } from '$lib/console/route-console';
	import {
		completenessOf,
		completenessSentence,
		untilNextUtcDay
	} from '$lib/console/completeness';
	import { stickStrip } from '$lib/console/strip';
	import { provideWindowSlot, type WindowSource } from '$lib/console/window-slot';

	let { data, children } = $props();

	// Read off the route rather than passed in by each page. Three pages naming
	// their own id is three places for it to be wrong, and the routes already
	// carry the address they answer at.
	const active = $derived(
		data.routes.find((route) => route.href.replace(/\/$/, '') === page.route.id)?.id ?? 'pipelines'
	);

	// Raw, because a source is an object of getters and a deep proxy of it would
	// be a copy of the route's state rather than the route's state. Only drawn
	// from: the slot decides which route holds it.
	let handed = $state.raw<WindowSource | null>(null);
	provideWindowSlot((source) => (handed = source));

	/** What the route loaded, read from the page rather than handed in, because
	 * the layout is drawn before the route's script runs. */
	const routeData = $derived(
		page.data as {
			chrome?: unknown;
		}
	);
	const chrome = $derived(consoleChromeOf(routeData));
	const workbench = $derived(chrome === 'workbench');

	const configured = consoleKnobs();

	/** The tabs the strip draws, from the band's route list. */
	const strip = $derived(stripRoutes(data.routes));
	const windowSource = $derived<WindowSource | null>(
		handed ?? {
			days: configured.default_window_days,
			presets: configured.window_presets,
			busy: false,
			ready: false,
			statusLine: null,
			monthsFor: () => 0,
			onChange: () => {}
		}
	);

	/** The reader's clock, which only a browser has. Null in the prerendered
	 * page, so that page dates the record and claims nothing about its age. */
	let now = $state<number | null>(null);

	// The answer can only change at a UTC midnight, so the page looks again then,
	// and whenever it is shown again - a laptop opened a day later has run no
	// timer in between.
	onMount(() => {
		let timer: ReturnType<typeof setTimeout> | undefined;
		const look = () => {
			clearTimeout(timer);
			now = Date.now();
			timer = setTimeout(look, untilNextUtcDay(now) + 1000);
		};
		const shown = () => {
			if (document.visibilityState === 'visible') look();
		};
		look();
		document.addEventListener('visibilitychange', shown);
		return () => {
			clearTimeout(timer);
			document.removeEventListener('visibilitychange', shown);
		};
	});

	const completeness = $derived(
		completenessOf(data.band.finishedAt, now, configured.completeness_grace_days)
	);

	/** The route's named groups, which are its jump links. A route with no
	 * groups, or one untitled group, has nothing to jump between. */
	const contents = $derived(routeConsole(active).panel_groups.filter((group) => group.title !== ''));
</script>

<section class="py-6" data-surface="operator" data-console-route={active} data-console-chrome={chrome}>
	<h1 id="console-top" class="text-[1.375rem] font-semibold tracking-[-0.011em] text-text" class:sr-only={workbench}>
		Console
	</h1>

	<!-- The space above the strip, drawn as its own box so that its bottom edge
	     is the strip's top edge in the flow. `strip.ts` watches it: once it has
	     scrolled off the top of the screen, the strip below it is stuck. -->
	{#if !workbench}<div class="strip-edge" aria-hidden="true"></div>{/if}
	<div class="console-strip" data-console-strip use:stickStrip>
		<div class="strip-tabs">
			<ConsoleNav routes={strip} {active} worst={data.band.worst?.id ?? null} />
		</div>
		{#if !workbench && windowSource !== null}
			<div class="strip-control">
				<WindowControl
					days={windowSource.days}
					presets={windowSource.presets}
					busy={windowSource.busy}
					ready={windowSource.ready}
					onChange={windowSource.onChange}
				/>
			</div>
		{/if}
	</div>
	<!-- The height the strip gives up when it sticks, held here instead so
	     nothing under the strip moves. Empty and zero tall until `strip.ts`
	     measures it. A margin on the strip itself would not do: it collapses
	     into the margin of whatever comes next, and the page moves by that. -->
	{#if !workbench}<div class="strip-give" aria-hidden="true"></div>{/if}

	{#if !workbench && completeness !== null}
		<!-- A sentence, not a badge, a colour or a grey timestamp. It is the same
		     words with or without a script; a browser only adds the count of days
		     missing, because only a browser knows what day it is. -->
		<p class="console-completeness" data-console-completeness={completeness.kind}>
			{completenessSentence(completeness)}
		</p>
	{/if}

	{#if !workbench}<ConsoleBand band={data.band} />{/if}

	<!-- Said once, above every panel, and only to a reader with no script.
	     The band above is real markup and stays readable; the panels below draw
	     rows a browser fetches, so with no script they keep their reserved shape
	     and stay empty. A page that let those boxes sit there unexplained would
	     be a page claiming the pipeline recorded nothing. -->
	{#if !workbench}<noscript>
		<p class="console-noscript" data-console-noscript>
			Panels drawn from the published record need JavaScript; with it off
			they keep their shape and stay empty.
		</p>
	</noscript>{/if}

	{#if !workbench && windowSource !== null}
		<WindowStatus
			days={windowSource.days}
			presets={windowSource.presets}
			monthsFor={windowSource.monthsFor}
			busy={windowSource.busy}
			ready={windowSource.ready}
			statusLine={windowSource.statusLine ?? null}
			record={windowSource.record ?? null}
		/>
	{/if}

	{#if !workbench && contents.length > 0}
		<!-- Named anchors, one per group heading, and each heading carries a `Top`
		     link back. They work with no script at every width, and a route with
		     several groups needs one destination per group - which is what a
		     floating back-to-top arrow could not give. -->
		<nav class="console-contents" aria-label="On this page" data-console-contents>
			<span class="contents-label" aria-hidden="true">On this page</span>
			<ul class="contents-list">
				{#each contents as group (group.id)}
					<li>
						<a class="contents-link" href="#{group.id}" data-console-contents-link={group.id}
							>{group.title}</a
						>
					</li>
				{/each}
			</ul>
		</nav>
	{/if}

	{@render children()}
</section>

<style>
	/* The gap between the title and the strip. It lives on this box rather than
	   as the strip's margin, so the box ends exactly where the strip starts. */
	.strip-edge {
		padding-top: var(--space-4);
	}

	/* The tabs and the days control. Below the wide breakpoint they wrap: the
	   tabs keep the whole row, and the control takes its own row under them. */
	.console-strip {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-2) var(--space-4);
		background: var(--color-bg);
	}

	.strip-give {
		block-size: var(--console-strip-give, 0px);
	}

	.strip-tabs {
		flex: 1 1 100%;
		min-inline-size: 0;
	}

	/* The value matches `frame.breakpoints_px[1]` in `config/appearance.json`; a
	   media query cannot read a custom property, which is the one place this
	   duplication is unavoidable. From there up the strip is one row - the tabs,
	   then the control at the trailing end - and it sticks, once a script is
	   there to keep the page still when it does. The rule the tabs stand on
	   moves here from the tab list, so it runs under the control too. */
	@media (min-width: 1024px) {
		.console-strip {
			flex-wrap: nowrap;
			border-block-end: 1px solid var(--item-edge);
		}

		/* The attribute is set by `strip.ts`, not by this template, so the
		   compiler cannot see it and has to be told it is real. */
		.console-strip:global([data-console-strip-live='yes']) {
			position: sticky;
			top: 0;
			z-index: 10;
		}

		.strip-tabs {
			flex: 1 1 auto;
		}

		.strip-control {
			flex: none;
		}
	}

	/* Quiet type, in the secondary colour, and the late form in the main text
	   colour rather than a warning colour: the words carry it. */
	.console-completeness {
		margin: var(--space-3) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.console-completeness[data-console-completeness='behind'] {
		color: var(--color-text);
	}

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

	.console-contents {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--space-1) var(--space-3);
		margin-top: var(--space-3);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
	}

	.contents-label {
		color: var(--color-text-tertiary);
	}

	.contents-list {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-1) var(--space-4);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	/* The console's own link: the accent, underlined under a pointer - the same
	   as the band's link and every route's carry line. */
	.contents-link {
		color: var(--color-accent);
	}

	.contents-link:hover {
		text-decoration: underline;
	}

	/* Workbench chrome runs to the window's edges: the section steps out of the
	   frame's gutter, the header keeps it, and the strip pads its own sides.
	   From the wide breakpoint the section is the column the route's workbench
	   fills, under a frame held to the window's height (`app.css`). */
	:global([data-console-chrome='workbench']) {
		padding-block: 0;
		margin-inline: calc(-1 * var(--gutter));
	}

	@media (min-width: 1024px) {
		:global([data-console-chrome='workbench']) {
			display: flex;
			flex-direction: column;
			flex: 1 1 0;
			min-block-size: 0;
		}
	}

	:global([data-console-chrome='workbench']) .console-strip {
		flex-wrap: nowrap;
		min-block-size: calc(var(--workbench-control) + 1px);
		padding-inline: var(--space-3);
		border-block-end: 1px solid var(--item-edge);
		background: var(--color-bg);
	}

	:global([data-console-chrome='workbench']) .strip-tabs {
		flex: 1 1 auto;
		min-inline-size: 0;
	}

	:global([data-console-chrome='workbench']) .console-strip:global([data-console-strip-live='yes']) {
		position: static;
	}
</style>
