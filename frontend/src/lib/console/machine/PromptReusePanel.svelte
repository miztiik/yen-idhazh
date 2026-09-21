<script lang="ts">
	/** The spread of prompt reuse and reading speed across an article's requests.
	 *
	 * Two tracks a request: how much of its prompt the server answered from what
	 * it already held, and how fast it read the rest. Both are spans over the
	 * items of the open window rather than one figure, because the finding is
	 * the spread - one request can read its whole prompt again while the next
	 * reuses almost all of its own, and their mean describes neither.
	 *
	 * **The tracks are built by iterating whatever requests the ledger carries.**
	 * Nothing here counts them. A ledger naming three draws three, and the day
	 * the pipeline merges two into one this panel draws one with no edit.
	 *
	 * No engine chart. A span is a band and a mark, which CSS draws before any
	 * script runs and at a fraction of the bytes an inlined drawing costs.
	 */
	import Panel from '$lib/components/Panel.svelte';
	import { spanTrack } from '$lib/charts/span-track';
	import type { PromptReuse } from '$lib/console/machine/prompt-reuse';
	import type { ChartConfig } from '$lib/server/config';

	let {
		reuse,
		days,
		windowDays,
		chart
	}: {
		reuse: PromptReuse;
		days: number;
		windowDays: number;
		chart: ChartConfig;
	} = $props();

	/** A share runs to 100 whatever the readings did, so a request that reused
	 * almost nothing draws short rather than filling its track. */
	const SHARE_CEILING = 100;

	const measured = $derived(reuse.requests.filter((request) => request.reuse !== null));
	/** One scale across every reading-speed track, so two requests' bands can be
	 * compared by looking. A track scaled to its own maximum would draw the
	 * slowest request and the fastest at the same length. */
	const readCeiling = $derived(
		Math.max(0, ...reuse.requests.map((request) => request.read?.high ?? 0))
	);

	const track = (low: number, high: number, at: number, from: number, ceiling: number | null) =>
		spanTrack(
			at,
			{ low, high, from, outOf: reuse.rowsRead },
			{ ceiling, width: chart.width_px }
		);

	const pct = (value: number) => `${value.toFixed(2)}%`;
	const rate = (value: number) => `${value.toFixed(2)} a second`;
</script>

<div data-windowed="machine-prompt-reuse" data-window-days={windowDays}>
<Panel
	heading="h3"
	id="prompt-reuse"
	title="How much text the model reads again, and how fast it reads"
	note="A request that reads its whole prompt again pays full price for text the server already holds, and the fix is that request rather than the machine - one span a request, over the items of the last {windowDays} days."
>
	<div
		data-prompt-reuse-requests={measured.length}
		data-prompt-reuse-items={reuse.items}
		data-prompt-reuse-floor={reuse.floor?.pct ?? ''}
		data-prompt-reuse-ceiling={reuse.ceiling?.pct ?? ''}
	>
		{#if measured.length === 0}
			<p class="absent" data-prompt-reuse-empty="none">
				No item in these {days} days recorded how much of a prompt the server read again, so there
				is no spread to draw.
			</p>
		{:else}
			{#if reuse.floor && reuse.ceiling}
				<p class="lead" data-prompt-reuse-lead>
					Over {reuse.items.toLocaleString('en')} of these {reuse.rowsRead.toLocaleString('en')}
					items, reuse runs from
					<strong>{pct(reuse.floor.pct)}</strong> on request {reuse.floor.place} to
					<strong>{pct(reuse.ceiling.pct)}</strong> on request {reuse.ceiling.place}, so one
					figure for the article would be the middle of those two and would move when neither
					end did.
				</p>
			{/if}

			<ul class="requests">
				{#each measured as request (request.name)}
					{@const reuseSpan = request.reuse}
					{@const readSpan = request.read}
					<li data-prompt-reuse-request={request.place} data-prompt-reuse-name={request.name}>
						<p class="request-name" id="reuse-{request.name}">Request {request.place}</p>

						{#if reuseSpan}
							{@const band = track(
								reuseSpan.low,
								reuseSpan.high,
								reuseSpan.median,
								reuseSpan.from,
								SHARE_CEILING
							)}
							<p class="track-name" id="reuse-read-again-{request.name}">Read again</p>
							{#if band.spanned && band.drawn}
								<div
									class="span-track"
									role="img"
									aria-labelledby="reuse-{request.name} reuse-read-again-{request.name}"
									data-reuse-low={reuseSpan.low}
									data-reuse-median={reuseSpan.median}
									data-reuse-high={reuseSpan.high}
									data-reuse-items={reuseSpan.from}
								>
									<span
										class="span-fill reuse"
										style="inset-inline-start: {band.start}; inline-size: {band.length}"
									></span>
									<span class="span-now" style="inset-inline-start: {band.at}"></span>
								</div>
							{/if}
							<p class="reading" data-reuse-reading={request.place}>
								{pct(reuseSpan.low)} to {pct(reuseSpan.high)}, middle item
								{pct(reuseSpan.median)}
								<span class="unit">
									on {reuseSpan.from.toLocaleString('en')} items{band.spanned && !band.drawn
										? '; every item read back the same share, so there is no band to draw'
										: `, against a track that runs to ${SHARE_CEILING}%`}.
								</span>
							</p>
						{/if}

						{#if readSpan}
							{@const band = track(
								readSpan.low,
								readSpan.high,
								readSpan.median,
								readSpan.from,
								readCeiling
							)}
							<p class="track-name" id="reuse-rate-{request.name}">Reading speed</p>
							{#if band.spanned && band.drawn}
								<div
									class="span-track"
									role="img"
									aria-labelledby="reuse-{request.name} reuse-rate-{request.name}"
									data-read-low={readSpan.low}
									data-read-median={readSpan.median}
									data-read-high={readSpan.high}
								>
									<span
										class="span-fill read"
										style="inset-inline-start: {band.start}; inline-size: {band.length}"
									></span>
									<span class="span-now" style="inset-inline-start: {band.at}"></span>
								</div>
							{/if}
							<p class="reading" data-read-reading={request.place}>
								{rate(readSpan.low)} to {rate(readSpan.high)}, middle item
								{rate(readSpan.median)}
								<span class="unit">
									in tokens, on {readSpan.from.toLocaleString('en')} items; every speed track
									on this panel runs to {rate(readCeiling)}, so two requests compare by
									looking.
								</span>
							</p>
						{:else}
							<p class="absent" data-read-absent={request.place}>
								No item in these {days} days recorded how fast this request read, which is a
								reading that did not survive rather than a request that took no time.
							</p>
						{/if}
					</li>
				{/each}
			</ul>

			<p class="basis" data-prompt-reuse-basis>
				The bar is the span over the window's items and the upright is the middle item. Requests
				are numbered in the order the ledger fills them, and the page draws one track pair for
				each request the ledger names - nothing here is written for a fixed number of them.
			</p>
		{/if}
	</div>
</Panel>
</div>

<style>
	.lead {
		margin: 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	.requests {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
		gap: var(--space-5);
		margin: var(--space-4) 0 0;
		padding: 0;
		list-style: none;
	}

	.request-name {
		margin: 0 0 var(--space-2);
		font-size: var(--text-sm);
		font-weight: 600;
		color: var(--color-text);
	}

	.track-name {
		margin: var(--space-3) 0 var(--space-1);
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		color: var(--color-text-secondary);
	}

	.span-track {
		position: relative;
		block-size: 1.5rem;
		border-radius: var(--radius-sm);
		background: var(--color-surface-sunken);
	}

	.span-fill {
		position: absolute;
		inset-block: 0.375rem;
		border-radius: var(--radius-sm);
	}

	/* The two colours this route already gives these quantities: reading is
	   `--chart-1` on the counterfactual and the read-against-written panels, and
	   what the server answered without reading is `--chart-3`. One quantity keeps
	   one colour down the page. */
	.span-fill.reuse {
		background: var(--chart-3);
	}

	.span-fill.read {
		background: var(--chart-1);
	}

	.span-now {
		position: absolute;
		inset-block: 0;
		inline-size: 2px;
		background: var(--color-text);
	}

	.reading {
		margin: var(--space-2) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		font-variant-numeric: tabular-nums;
		color: var(--color-text);
	}

	.unit {
		display: block;
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		font-variant-numeric: normal;
		color: var(--color-text-secondary);
	}

	.absent,
	.basis {
		margin: var(--space-3) 0 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}
</style>
