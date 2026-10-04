<script lang="ts">
	/** Where an operator can go, and what is worst on each route before he goes.
	 *
	 * Directly under the page title and above the band since 2026-08-31. Chrome
	 * above content is the one ordering a reader never has to learn, and the
	 * band's worst fact links into this strip - which a phone reader could not
	 * find 337px below it.
	 *
	 * Real anchors, one per prerendered route. Not tabs holding hidden panels:
	 * a tab strip that switches with script is a page that says nothing with
	 * script off, and every panel it hides still ships in the document.
	 *
	 * Every label carries its own worst state, computed at build time. Without
	 * it a route is where a metric goes to die - nobody opens a page to find out
	 * whether it was worth opening.
	 *
	 * **It took a fourth and a fifth route on 2026-09-12, and the basis is what
	 * moved.** At `14rem` one tab filled a 360px phone, so five would have stood
	 * five deep directly above the band.
	 *
	 * **From `frame.breakpoints_px[1]` up it is one row, however many routes
	 * there are.** The strip sticks to the top of the screen there, and a stuck
	 * strip that wrapped would cover a second row of every screen. So the list
	 * scrolls sideways when the tabs are wider than the row, and no label is
	 * shortened to make them fit. The list opens with the reader's own tab whole,
	 * because a page that cannot show which route it is has lost the strip's
	 * first job; and with the band's worst route in view too wherever both fit -
	 * the one fact on the strip the band cannot give once the band has scrolled
	 * away. Where they do not both fit, the band under the strip still names the
	 * worst route.
	 *
	 * **The sixth route, Data explorer, is live.** The layout hands this strip
	 * `stripRoutes()` of the band's routes; the old flag was removed with the page.
	 */
	import { onMount } from 'svelte';
	import { base } from '$app/paths';
	import type { ConsoleRoute, RouteId } from '$lib/console/band';

	let {
		routes,
		active,
		worst = null
	}: {
		routes: ConsoleRoute[];
		active: RouteId;
		/** The route the band names as worst, or null when nothing is. */
		worst?: RouteId | null;
	} = $props();

	let list = $state<HTMLUListElement>();

	onMount(() => {
		if (list === undefined) return;
		if (list.scrollWidth <= list.clientWidth) return;
		const shown = list.getBoundingClientRect();
		// The sideways scrolls, from where the list stands now, that leave one tab
		// whole: from the least that brings its right edge in to the most that
		// keeps its left edge in.
		const whole = (id: RouteId | null): [number, number] | null => {
			const tab = id === null ? null : list?.querySelector(`[data-console-tab="${id}"]`);
			if (tab === null || tab === undefined) return null;
			const box = tab.getBoundingClientRect();
			return [box.right - shown.right, box.left - shown.left];
		};
		const own = whole(active);
		if (own === null) return;
		let [least, most] = own;
		const named = worst === active ? null : whole(worst);
		if (named !== null && Math.max(least, named[0]) <= Math.min(most, named[1])) {
			least = Math.max(least, named[0]);
			most = Math.min(most, named[1]);
		}
		list.scrollLeft += Math.min(Math.max(0, least), most);
	});
</script>

<nav class="console-nav" aria-label="Console sections" data-console-nav>
	<ul class="tabs" bind:this={list}>
		{#each routes as route (route.id)}
			<li class="tab-slot">
				<a
					class="tab"
					href="{base}{route.href}"
					title={route.description}
					aria-current={route.id === active ? 'page' : undefined}
					data-console-tab={route.id}
					data-console-tab-active={route.id === active ? 'true' : null}
				>
					<span class="tab-head">
						<span class="tab-label">{route.label}</span>
						{#if route.worst || route.id === worst}
							<!-- No health colour, ever. Green, amber and red on a label
							     would say a route is failing, and a route is a noun. The
							     worst of them says so in a word instead, and says it at
							     the top of the page too, so nothing reflows when the strip
							     sticks. -->
							<span class="tab-state"
								>{#if route.id === worst}<span
										class="tab-worst-mark"
										data-console-tab-worst-mark>{route.worst ? 'Worst:' : 'Worst'}</span
									>{' '}{/if}{#if route.worst}<span
										class="tab-worst"
										data-console-tab-worst={route.id}>{route.worst}</span
									>{/if}</span
							>
						{/if}
					</span>
					<span class="tab-line">{route.description}</span>
				</a>
			</li>
		{/each}
	</ul>
</nav>

<style>
	/* The rule the tabs stand on. From the wide breakpoint up it moves to the
	   strip, which is one row with the days control, so the line runs under both.
	   It is the reading item's own hairline, which is the stronger of the two
	   rules on the dark ground. */
	.console-nav {
		min-inline-size: 0;
		border-block-end: 1px solid var(--item-edge);
	}

	.tabs {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	/* 8rem is 128px at a 16px root, so two tabs and the gap between them fit the
	   288px content box of a 320px phone - the narrowest screen still in use -
	   and five stand three deep rather than five. It was 14rem, 224px, one tab to
	   a row, while the strip held three. Measured 2026-09-12 off the built page:
	   9rem cleared 360 and still stacked five deep at 320, which is the same
	   defect one screen narrower. */
	.tab-slot {
		display: flex;
		flex: 1 1 8rem;
		min-inline-size: 0;
	}

	/* The whole block is the target, not the word at the top of it. The touch
	   target is the 2.75rem floor, so the padding pays for looks and not for
	   reach - and the three rows of tabs above the band on a phone is where every
	   pixel of it is charged three times. It fills its slot, which is as tall as
	   the row, so the active route's rule sits on one line under every tab - a
	   tab with no worst state included. */
	.tab {
		flex: 1 1 auto;
		min-inline-size: 0;
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-block-size: 2.75rem;
		padding: var(--space-2) var(--space-3);
		border-radius: var(--radius-md) var(--radius-md) 0 0;
		/* Reserved on every tab, so the active one does not push the strip down
		   by three pixels when the operator moves between routes. */
		border-block-end: 3px solid transparent;
		color: var(--color-text-secondary);
		text-decoration: none;
	}

	.tab:hover {
		background: var(--color-surface);
	}

	/* Inside the tab rather than around it: from the wide breakpoint up the list
	   scrolls sideways, and a scrolling list clips whatever reaches past it. */
	.tab:focus-visible {
		outline: 2px solid var(--color-focus);
		outline-offset: -2px;
	}

	/* The one thing that differs between routes: a 3px rule from the categorical
	   ramp. Categorical because it names a place and passes no verdict. */
	.tab[aria-current='page'] {
		border-block-end-color: var(--chart-1);
		background: var(--color-surface);
		color: var(--color-text);
	}

	.tab-head {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--space-2);
	}

	.tab-label {
		font-size: var(--text-base);
		line-height: var(--leading-base);
		font-weight: 600;
	}

	.tab-worst {
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		color: var(--color-text-secondary);
	}

	/* The one word that tells the band's worst route from the others, in weight
	   and the main text colour rather than in a verdict colour. */
	.tab-worst-mark {
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		font-weight: 600;
		color: var(--color-text);
	}

	/* Hidden by default and shown from the wide breakpoint, which is the one
	   three other components already use. Below it a tab is too narrow to carry
	   a sentence: measured 2026-09-12 off the built page, at 800px each tab is
	   141px and the description wraps to six lines, so the strip is 168px where
	   the same strip without it is 86px - widening the window made the chrome
	   taller, which is the discontinuity a reader notices and cannot explain.
	   The line is not lost below: it is still the anchor's `title`, and the page
	   it opens prints it in full. What a hidden line costs is the one-line
	   summary a reader gets before choosing, which is why every label is one
	   word. */
	.tab-line {
		display: none;
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		color: var(--color-text-tertiary);
	}

	/* The value matches `frame.breakpoints_px[1]` in `config/appearance.json`; a
	   media query cannot read a custom property, which is the one place this
	   duplication is unavoidable. */
	@media (min-width: 1024px) {
		.console-nav {
			border-block-end: 0;
		}

		/* One row at every count of tabs. A tab keeps the width the longer of its
		   label and its worst state needs and shares whatever the row has left, and
		   when the row has nothing left the list scrolls rather than wrapping or
		   shortening a label. */
		.tabs {
			flex-wrap: nowrap;
			overflow-x: auto;
			overscroll-behavior-x: contain;
			scrollbar-width: thin;
		}

		.tab-slot {
			flex: 1 1 0;
			min-inline-size: max-content;
		}

		/* The worst state stands on its own line under the label, never broken
		   inside the phrase, so a tab is as wide as the longer line rather than as
		   both side by side. Measured 2026-09-27 off the built page: side by side,
		   the landing route showed four of five tabs whole at every width from
		   1366 to 1920; stacked, all five from 1366. What it costs is one line of
		   every tab's height. */
		.tab-head {
			flex-direction: column;
			align-items: flex-start;
			gap: 0;
		}

		.tab-state {
			white-space: nowrap;
		}

		/* The description takes the width its tab already has and never widens
		   it, so a tab is as wide as its label and its worst state and no wider. */
		.tab-line {
			display: block;
			contain: inline-size;
		}
	}

	/* While the strip is stuck the description goes. It is the anchor's `title`,
	   and it is back the moment the strip returns to the top. */
	:global([data-console-strip-stuck='yes']) .tab-line {
		display: none;
	}

	:global([data-console-chrome='workbench']) .console-nav {
		border-block-end: 0;
	}

	:global([data-console-chrome='workbench']) .tabs {
		flex-wrap: nowrap;
		gap: var(--space-1);
		overflow-x: auto;
		overscroll-behavior-x: contain;
		scrollbar-width: thin;
	}

	:global([data-console-chrome='workbench']) .tab-slot {
		flex: 0 0 auto;
		min-inline-size: max-content;
	}

	:global([data-console-chrome='workbench']) .tab {
		min-block-size: var(--workbench-control);
		padding: var(--space-1) var(--space-3);
		border-radius: 0;
	}

	:global([data-console-chrome='workbench']) .tab-head {
		flex-direction: row;
		align-items: center;
	}

	:global([data-console-chrome='workbench']) .tab-label {
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		white-space: nowrap;
	}

	:global([data-console-chrome='workbench']) .tab-state,
	:global([data-console-chrome='workbench']) .tab-line {
		display: none;
	}
</style>
