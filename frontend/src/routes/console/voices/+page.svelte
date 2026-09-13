<script lang="ts">
	/** Who supplied the day, and what the ranking makes of them.
	 *
	 * One panel, one published file. Every figure here was reduced over
	 * `collect.reliability_window_days` when the run happened, so there is no
	 * window control: a control that offered a span the numbers were not taken
	 * over would be a control that lies.
	 */
	import { base } from '$app/paths';

	let { data } = $props();

	const standing = $derived(data.standing);
	const pct = (share: number) => `${Math.round(share * 100)}%`;
</script>

<div data-console-panels="voices">
	<p class="console-carry" data-console-carry="pipelines">
		{data.carries.voices}
		<a class="carry-link" href="{base}/console/">Pipelines &rarr;</a>
	</p>

	<h2 class="console-h2">What the ranking makes of each feed</h2>

	{#if standing === null}
		<div class="console-panel" data-console-empty="voices">
			<p class="empty-lead">No run has published a source record yet.</p>
			<p class="empty-note">
				This page draws one file, <code>source-health.json</code>, which the pipeline writes at
				the end of a run. Until a run finishes there is nothing to draw here, which is not the
				same as every feed being fine.
			</p>
		</div>
	{:else}
		<p class="headline" data-voices-headline>{standing.headline}</p>

		<div class="console-panel" data-voices="reliability">
			<h3 class="console-h3">How far the ranking discounts each feed</h3>
			<p class="lead" data-voices-lead>
				Every feed carries a weight, and the ranking multiplies its stories by it. A feed that
				answers with articles keeps all of it. A feed that keeps coming back empty or unreachable
				loses some, down to {pct(standing.floor)} and no further. The bar is that weight, the mark
				on it is the floor, and the count beside it is how many reads the figure was taken over -
				in the last {standing.windowDays} days.
			</p>

			{#if standing.counted === 0}
				<p class="empty-lead" data-voices="none">No feed is active, so there is no weight to draw.</p>
			{:else}
				<ol class="standings" data-voices-drawn={standing.feeds.length}>
					{#each standing.feeds as feed (feed.sourceId)}
						<li
							class="standing"
							data-voices-feed={feed.sourceId}
							data-voices-factor={feed.factor.toFixed(3)}
							data-voices-reads={feed.reads}
							data-voices-floored={feed.onTheFloor ? 'yes' : 'no'}
						>
							<span class="name">
								<span class="title">{feed.title}</span>
								<span class="vertical">{feed.vertical}</span>
							</span>
							{#if feed.marks === null}
								<span class="track track--empty" data-voices-cell="bar">
									<span class="dash" aria-hidden="true">&mdash;</span>
								</span>
								<span class="figure figure--absent">
									not measured
									<span class="denominator">0 reads</span>
								</span>
							{:else}
								<span
									class="track"
									data-voices-cell="bar"
									data-band={feed.marks.band}
									role="img"
									aria-label="{feed.title} keeps {pct(feed.factor)} of its weight, against a floor of {pct(
										standing.floor
									)}"
								>
									<span class="fill" style="width: {feed.marks.valuePercent}"></span>
									<span class="marker" style="left: {feed.marks.markerPercent}"></span>
								</span>
								<span class="figure">
									{pct(feed.factor)}
									<span class="denominator">{feed.reads} reads</span>
								</span>
							{/if}
						</li>
					{/each}
				</ol>

				{#if standing.hidden > 0}
					<p class="note" data-voices-more>
						{standing.hidden} more feeds are not drawn, {standing.hiddenOnTheFloor} of them on the
						floor. The list is read from the top, and its tail is a number rather than another page
						of rows.
					</p>
				{/if}

				{#if standing.unmeasured > 0}
					<p class="note" data-voices-unmeasured={standing.unmeasured}>
						{standing.unmeasured} of {standing.counted} feeds have no read to judge in the last {standing.windowDays}
						days, so each prints a dash rather than a weight. The ranking gives them full weight in
						the meantime: not being asked is not the same as answering badly.
					</p>
				{/if}
			{/if}

			<p class="note" data-voices-basis>
				Published by run {standing.runId} at {standing.generatedAt}. The weight is the one that run
				applied, read from the record rather than worked out again here.
			</p>
		</div>
	{/if}
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

	/* One sentence above the panel, not inside it: it is the verdict over every
	   figure below, and a verdict indented under one panel reads as that panel's. */
	.headline {
		margin: 0 0 var(--space-4);
		font-size: var(--text-base);
		line-height: var(--leading-base);
		color: var(--color-text);
	}

	.lead {
		margin: 0 0 var(--space-4);
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.note {
		margin: var(--space-3) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.standings {
		display: grid;
		gap: var(--space-2);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.standing {
		display: grid;
		grid-template-columns: minmax(7rem, 13rem) minmax(4rem, 1fr) auto;
		gap: var(--space-3);
		align-items: center;
	}

	.name {
		display: flex;
		min-width: 0;
		flex-direction: column;
	}

	.title {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.vertical,
	.denominator {
		font-size: var(--text-xs);
		color: var(--color-text-secondary);
	}

	/* The track is 1.0 wide because the figure cannot exceed 1.0. Two feeds'
	   bars are therefore on one scale, which is the whole point of drawing a
	   share as a bar rather than printing it. */
	.track {
		position: relative;
		display: block;
		height: 0.75rem;
		border-radius: var(--radius-sm);
		background: var(--color-surface-sunken, var(--color-border));
	}

	.track--empty {
		display: grid;
		background: none;
		place-items: center;
	}

	.dash {
		color: var(--color-text-secondary);
	}

	.fill {
		position: absolute;
		border-radius: var(--radius-sm);
		background: var(--color-ok);
		inset: 0 auto 0 0;
	}

	.track[data-band='near'] .fill {
		background: var(--color-warn);
	}

	.track[data-band='past'] .fill {
		background: var(--color-bad);
	}

	.marker {
		position: absolute;
		top: -0.2rem;
		bottom: -0.2rem;
		width: 2px;
		background: var(--color-text);
	}

	.figure {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		font-variant-numeric: tabular-nums;
	}

	.figure--absent {
		color: var(--color-text-secondary);
	}

	/* A phone puts the bar on its own line rather than squeezing three columns
	   into 34rem, which is what pushed the page sideways when it was tried. */
	@media (max-width: 34rem) {
		.standing {
			grid-template-columns: 1fr auto;
		}

		.track {
			grid-column: 1 / -1;
		}
	}
</style>
