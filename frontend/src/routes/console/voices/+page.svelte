<script lang="ts">
	/** Who supplied the day - the route, opened before its panels.
	 *
	 * **It is deliberately empty and it is deliberately here.** The strip took a
	 * fourth and a fifth tab on 2026-09-12, and a tab naming a page nobody can
	 * reach is worse than three tabs. So the route answers 200, carries its own
	 * heading and prints a named absence saying which row fills it.
	 *
	 * It draws no panel and fetches nothing, which is why it has no window
	 * control: the control governs the panels below it and there are none.
	 */
	import { base } from '$app/paths';

	let { data } = $props();
</script>

<div data-console-panels="voices">
	<!-- One sentence, no chart. Until this route has figures of its own it is
	     the only number on the page, and it is derived rather than stated. -->
	<p class="console-carry" data-console-carry="pipelines">
		{data.carries.voices}
		<a class="carry-link" href="{base}/console/">Pipelines &rarr;</a>
	</p>

	<h2 class="console-h2">The feeds that supplied the day</h2>

	<div class="console-panel" data-console-empty="voices">
		<p class="empty-lead">
			This route will carry who supplied the day: how far the ranker discounts each
			feed, which feeds have too short a record to judge, and how much of what each
			one offered was worth publishing.
		</p>
		<p class="empty-note">
			Nothing is drawn here yet. The panels are specified by row #13 of
			<code>TODO/20260910-25-placement-plan.md</code>. Until they land, which feeds
			broke and which are resting is on Pipelines.
		</p>
	</div>
</div>

<style>
	/* The lead carries the weight, because with no figure on the page it is the
	   one thing the eye lands on (design-system.md). The note under it is the
	   secondary voice every console panel uses for a caveat. */
	.empty-lead {
		margin: 0;
		font-size: var(--text-base);
		line-height: var(--leading-base);
		color: var(--color-text);
	}

	.empty-note {
		margin: var(--space-3) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	code {
		font-family: var(--font-data);
		font-size: 0.9em;
		overflow-wrap: anywhere;
	}
</style>
