<script lang="ts">
	/** An item with no visual is simply shorter.
	 *
	 * No placeholder and no reserved slot: a grey rectangle makes "we correctly
	 * decided this needed no picture" look identical to "the image failed", which
	 * is the wrong signal on a page whose product is trust. Two items in three
	 * carry no visual, so this is the default shape, not a fallback.
	 *
	 * **The reader's browser draws the chart and the pipeline never draws one**
	 * (maintainer ruling, 2026-09-13,
	 * `docs/architecture/publishing/visuals.md`). A story arrives carrying a
	 * pointer at its marks; this component asks for that file when the story
	 * comes near, checks the shape, and draws it. Nothing is rendered at build
	 * time and no drawing is committed.
	 *
	 * **What the reader gives up, stated where it lands.** A reader with
	 * JavaScript off gets no chart AND no sentence, where a committed SVG used to
	 * be markup inside the document itself. The figure below only exists once the
	 * marks have arrived, so there is no path on which a script-less page carries
	 * either one - which is a real loss and a different row's to answer. And every
	 * day published before 2026-09-13 loses its chart for every reader, because no
	 * marks file was ever written for one and back-filling would mean re-fetching
	 * source pages that have since moved.
	 *
	 * **No fact is left to a pointer.** The figure is one tab stop, and its
	 * accessible name is written from the same `Drawing` the marks are drawn from
	 * - so what a keyboard reaches and what an eye reaches are one set by
	 * construction rather than by two derivations agreeing. One tab stop for a
	 * chart and never one per mark: a day runs to hundreds of stories, and a mark
	 * apiece would make the stream something a keyboard cannot get past. The ring
	 * is the scale's own step rather than a rule in the block below, because a px
	 * size in an authored style block ignores a reader who set their browser text
	 * larger and `frontend/tests/tokens.spec.ts` refuses one.
	 *
	 * **The drawing is written by Svelte from geometry `$lib/visual/bar`
	 * computed**, so the marks are ordinary elements in this component's own
	 * subtree. They take the page's tokens through plain scoped CSS rather than
	 * through `:global` overrides of a renderer's class vocabulary, and every
	 * string a model cut out of a stranger's page lands as a text node rather
	 * than as markup (Guardrail #11).
	 *
	 * **The drawing takes the width the card gives it.** The
	 * figure's content box is measured first and every mark is placed in it, so
	 * one drawn unit is one CSS pixel and there is no scale factor between what a
	 * token says and what a reader sees. Before this the drawing was laid out at
	 * a fixed 720 units and stretched to fit, so a `--text-xs` string resolved at
	 * 4.8 CSS px on a 390 px phone - the right size in a coordinate space nobody
	 * reads. Height follows readable content and the visible viewport, not a
	 * fixed canvas or density budget. A short viewport uses normal page scrolling.
	 */
	import { base } from '$app/paths';
	import { navigating } from '$app/state';
	import { isVisualData, publishedVisualData, refusedVisualData } from '$lib/payload/drawing';
	import type { DigestVisual, VisualData } from '$lib/payload/types';
	import { numberFormatter, type NumberFormatConfig } from '$lib/number-format';
	import { whenNear } from '$lib/reveal';
	import type { StoryChartGeometryConfig } from '$lib/server/config';
	import PartsOfOne from '$lib/charts/d3/PartsOfOne.svelte';
	import { drawVisual, statedDrawing, type Drawing } from '$lib/visual/bar';
	import { fitChartGeometry, fitChartTicks, whenChartFits, type ChartRoom } from '$lib/visual/viewport';

	let {
		visual,
		numberFormat,
		storyChartGeometry,
		chartTickDensity
	}: {
		visual: DigestVisual | null;
		numberFormat: NumberFormatConfig;
		storyChartGeometry: StoryChartGeometryConfig;
		chartTickDensity: number;
	} = $props();
	const formatNumber = $derived(numberFormatter(numberFormat));

	/** The file this story's marks are in, or null when it has none to ask for.
	 *
	 * A day published before the marks existed carries no `data_path`, and so
	 * does a visual whose file did not land. Both read the same way and both are
	 * designed states: the story has no chart.
	 */
	const wanted = $derived(
		visual?.state === 'rendered' && visual.data_path ? visual.data_path : null
	);

	/** The result for the current path, or null while its request has not settled. */
	let loaded = $state<{ file: string; data: VisualData | null } | null>(null);
	let near = $state(false);
	let settled = $state<string | null>(null);
	/** How much room the card gives the drawing, or 0 before it has been measured. */
	let room = $state(0);
	let chartRoom = $state<ChartRoom | null>(null);
	const currentLoad = $derived(loaded?.file === wanted ? loaded.data : null);
	const fittedGeometry = $derived(currentLoad && chartRoom
		? fitChartGeometry(currentLoad, storyChartGeometry, chartRoom) : storyChartGeometry);
	const fittedTicks = $derived(currentLoad && chartRoom
		? fitChartTicks(currentLoad, fittedGeometry, chartRoom.textHeight, chartTickDensity) : chartTickDensity);
	const drawing = $derived<Drawing | null>(
		currentLoad && room > 0
			? drawVisual(currentLoad, room, formatNumber, numberFormat, fittedTicks, fittedGeometry)
			: null
	);
	/** Every figure the bars are drawn at, in one sentence, for a reader who is
	 * not looking at them. It is the whole of what the tab stop below announces. */
	const stated = $derived(drawing ? statedDrawing(drawing) : '');

	/** Read one published path, refusing any document that is not current and valid.
	 *
	 * **It refuses rather than guesses, and refusing is free.** A degrade path
	 * that draws something approximate is how a wrong chart reaches a reader, and
	 * the product is trust. The path is matched before it is joined onto `base`,
	 * for the same reason `dayUrl` matches a date: it is about to become an
	 * address.
	 *
	 * **`__ASSET_BASE_URL__` moves where the file is asked for and nothing
	 * else.** It is `visuals.asset_base_url`, injected at build time, and it
	 * ships empty - so the join is `base`, this site, exactly as it was. Naming a
	 * host there takes the marks a reader scrolls to off the 1 GB published
	 * ceiling without touching anything else: the bytes still arrive as data and
	 * are still checked here. The origin comes from our config and can never come
	 * from a payload.
	 */
	async function read(file: string, signal: AbortSignal): Promise<VisualData | null> {
		if (!publishedVisualData(file)) {
			console.warn(`[digest] ${file}: not a published visual path, so it is not drawn`);
			return null;
		}
		try {
			const response = await fetch(`${__ASSET_BASE_URL__ || base}/${file}`, { signal });
			if (!response.ok) {
				console.warn(`[digest] ${file}: not available (${response.status}), so it is not drawn`);
				return null;
			}
			const data: unknown = await response.json();
			if (!isVisualData(data)) {
				console.warn(`[digest] ${file}: ${refusedVisualData(data)}, so it is not drawn`);
				return null;
			}
			return data;
		} catch (error) {
			// A story the reader scrolled away from cancelled its own request. That
			// is the page working, so it says nothing.
			if (signal.aborted) return null;
			console.warn(`[digest] ${file} could not be read, so it is not drawn`, error);
			return null;
		}
	}

	/** Ask for the marks once the story is nearly on screen.
	 *
	 * The `img` this path replaced carried `loading="lazy"`, so a browser asked
	 * for a drawing only when the reader was near it. A plain fetch on mount
	 * throws that away, and the case where it hurts is not the ordinary one: a
	 * reader following `/<date>/#<story>` pages the stream down to that story, so
	 * the whole prefix mounts at once.
	 *
	 * **Every waiting story shares one watcher**, which lives in `$lib/reveal`
	 * and holds the margin. A story built its own until 2026-09-06, so a day that
	 * published more visuals held more watchers - a cost that rose because a run
	 * published more, which is what Guardrail #12 refuses.
	 *
	 * **A story that leaves the page takes its request with it.** Unmount stops
	 * the watch and aborts the fetch, so a reader scrolling fast is not still
	 * downloading marks for stories that are gone, and an answer that was already
	 * on its way is not written into a component nobody is reading.
	 * Navigation also pauses new requests and aborts pending ones, so the page
	 * being left cannot compete with the destination's first payload.
	 */
	$effect(() => {
		const file = wanted;
		if (
			!near || !file || navigating.to !== null ||
			settled === file
		) return;
		const request = new AbortController();
		void read(file, request.signal).then((data) => {
			if (!request.signal.aborted) {
				settled = file;
				loaded = { file, data };
			}
		});
		return () => {
			request.abort();
		};
	});

	function askWhenNear(node: Element): { destroy: () => void } {
		const forget = whenNear(node, () => { near = true; });
		return {
			destroy: forget
		};
	}
	/** Follow the card's own content box, and redraw whenever it moves.
	 *
	 * The figure is measured rather than the svg inside it, because the figure's
	 * width does not depend on what it holds - so the reading is stable on the
	 * frame the marks land in, before a mark is placed. Every chart on the page
	 * shares one watcher. Scrolling never changes this measurement.
	 */
	function measured(node: Element): { destroy: () => void } {
		const forget = whenChartFits(node, (next) => {
			room = next.width;
			if (!chartRoom || chartRoom.width !== next.width ||
				chartRoom.height !== next.height || chartRoom.textHeight !== next.textHeight) {
				chartRoom = next;
			}
		});
		return { destroy: forget };
	}
</script>

{#if currentLoad}
	<!-- The figure takes the focus, not the marks inside it: `role="img"` replaces
	     its whole subtree with one name, so a bar given its own tab stop would be
	     a stop announcing nothing. It is not a control and it is still focusable,
	     because the alternative is a chart a keyboard cannot reach at all. -->
	<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
	<figure
		class="visual my-4 overflow-hidden rounded-md border border-rule bg-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
		tabindex="0"
		role="img"
		aria-label={stated}
		use:measured
	>
		{#if drawing}
			{#if drawing.title}
				<div class="chart-title px-3 pt-3 text-sm font-semibold leading-snug text-text">{drawing.title}</div>
			{/if}
			{#if drawing.type === 'stacked_bar'}
				<div class="px-3 py-3">
					<PartsOfOne
						geometry={drawing.geometry}
						empty={null}
						name={`story-${currentLoad.item_id}`}
						label={stated}
						width={drawing.width}
						height={chartRoom?.height ?? 0}
						readout={[drawing.readout]}
						separateSegments={true}
						showTotal={false}
					/>
				</div>
			{:else}
			<svg
				viewBox="0 0 {drawing.width} {drawing.height}"
				width={drawing.width}
				height={drawing.height}
				role="presentation"
			>
				{#if drawing.type === 'bar'}
					{#each drawing.bars as bar (bar.y)}
						<text class="name" class:emphasized={bar.emphasized} x="0" y={bar.label}>{bar.name}</text>
						<rect
							class="bar"
							class:emphasized={bar.emphasized}
							stroke-width={storyChartGeometry.mark_outline_width_px}
							x="0"
							y={bar.y}
							width={bar.width}
							height={bar.height}
							rx={storyChartGeometry.bar_corner_radius_px}
						/>
						<text class="figure" x={bar.figure} y={bar.y + bar.height / 2}>{bar.displayed}</text>
					{/each}
					<line
						class="axis"
						stroke-width={storyChartGeometry.axis_line_width_px}
						x1="0"
						y1={drawing.baseline}
						x2={drawing.width}
						y2={drawing.baseline}
					/>
					{#if drawing.unit}
						<text class="unit" x="0" y={drawing.baseline + storyChartGeometry.axis_label_offset_px}>{drawing.unit}</text>
					{/if}
				{:else if drawing.type === 'dot'}
					{#each drawing.dots as dot (dot.y)}
						<text class="name" class:emphasized={dot.emphasized} x="0" y={dot.labelY}>{dot.name}</text>
						<circle
							class="dot"
							class:emphasized={dot.emphasized}
							stroke-width={storyChartGeometry.mark_outline_width_px}
							cx={dot.x}
							cy={dot.y}
							r={dot.radius}
						/>
						<text class="figure" x={dot.valueX} y={dot.y}>{dot.displayed}</text>
					{/each}
					<line
						class="axis"
						stroke-width={storyChartGeometry.axis_line_width_px}
						x1={storyChartGeometry.dot_radius_px}
						y1={drawing.baseline}
						x2={drawing.axisEnd}
						y2={drawing.baseline}
					/>
					{#if drawing.unit}
						<text class="unit" x="0" y={drawing.baseline + storyChartGeometry.axis_label_offset_px}>{drawing.unit}</text>
					{/if}
				{:else if drawing.type === 'line'}
					{#each drawing.axis.ticks as tick (tick.value)}
						<line
							class="grid"
							stroke-width={storyChartGeometry.axis_line_width_px}
							x1={drawing.frame.left}
							y1={tick.at}
							x2={drawing.frame.right}
							y2={tick.at}
						/>
						{#if tick.text}
							<text
								class="figure value-tick"
								text-anchor="end"
								x={drawing.frame.left - storyChartGeometry.value_gap_px}
								y={tick.at}
							>{tick.text}</text>
						{/if}
					{/each}
					<line
						class="axis"
						stroke-width={storyChartGeometry.axis_line_width_px}
						x1={drawing.frame.left}
						y1={drawing.frame.bottom}
						x2={drawing.frame.right}
						y2={drawing.frame.bottom}
					/>
					{#each drawing.lines as line (line.name)}
						<path
							class={`series-line chart-${line.color}`}
							d={line.path}
							stroke-dasharray={line.dasharray}
							stroke-width={storyChartGeometry.line_width_px}
						/>
						{#each line.points as point (`${line.name}-${point.date}`)}
							<circle
								class={`line-point chart-${line.color}`}
								class:emphasized={point.emphasized}
								stroke-width={storyChartGeometry.mark_outline_width_px}
								cx={point.x}
								cy={point.y}
								r={storyChartGeometry.dot_radius_px}
							/>
						{/each}
					{/each}
					{#each drawing.ticks as tick (tick.index)}
						<line
							class="axis"
							stroke-width={storyChartGeometry.axis_line_width_px}
							x1={drawing.columns[tick.index]}
							y1={drawing.frame.bottom}
							x2={drawing.columns[tick.index]}
							y2={drawing.frame.bottom + storyChartGeometry.axis_line_width_px * 4}
						/>
						<text
							class="date-label"
							text-anchor={tick.anchor}
							x={drawing.columns[tick.index]}
							y={drawing.frame.bottom + storyChartGeometry.axis_label_offset_px}
						>{tick.text}</text>
					{/each}
					{#if drawing.unit}
						<text class="unit" x="0" y={storyChartGeometry.line_axis_margin_top_px / 2}>
							{drawing.unit}
						</text>
					{/if}
				{:else if drawing.type === 'scatter' || drawing.type === 'bubble'}
					{#each drawing.y.ticks as tick (tick.value)}
						<line class="grid" stroke-width={storyChartGeometry.axis_line_width_px}
							x1={drawing.frame.left} x2={drawing.frame.right} y1={tick.at} y2={tick.at} />
						{#if tick.text}
							<text class="figure value-tick" text-anchor="end"
								x={drawing.frame.left - storyChartGeometry.value_gap_px} y={tick.at}>{tick.text}</text>
						{/if}
					{/each}
					<line class="axis" stroke-width={storyChartGeometry.axis_line_width_px}
						x1={drawing.frame.left} x2={drawing.frame.right}
						y1={drawing.frame.bottom} y2={drawing.frame.bottom} />
					<line class="axis" stroke-width={storyChartGeometry.axis_line_width_px}
						x1={drawing.frame.left} x2={drawing.frame.left}
						y1={drawing.frame.top} y2={drawing.frame.bottom} />
					{#each drawing.x.ticks as tick (tick.value)}
						{#if tick.text}
							<text class="figure value-tick" text-anchor="middle"
								x={tick.at} y={drawing.frame.bottom + storyChartGeometry.axis_label_offset_px}>{tick.text}</text>
						{/if}
					{/each}
					<text class="unit" x={drawing.frame.left} y={drawing.frame.top / 2}>
						y{drawing.yUnit ? ` (${drawing.yUnit})` : ''}
					</text>
					<text class="unit" text-anchor="end" x={drawing.frame.right}
						y={drawing.height - storyChartGeometry.value_gap_px}>
						x{drawing.xUnit ? ` (${drawing.xUnit})` : ''}
					</text>
					{#if drawing.type === 'bubble'}
						{#each drawing.points as point (point.label)}
							<circle class="bubble-point" class:emphasized={point.emphasized}
								stroke-width={storyChartGeometry.mark_outline_width_px}
								cx={point.cx} cy={point.cy} r={point.radius}>
								<title>{point.label}: x {point.statedX} {drawing.xUnit ?? ''},
									y {point.statedY} {drawing.yUnit ?? ''}, area
									{point.statedSize} {drawing.sizeUnit ?? ''}</title>
							</circle>
						{/each}
					{:else}
						{#each drawing.points as point (point.label)}
							<circle class="scatter-point" class:emphasized={point.emphasized}
								stroke-width={storyChartGeometry.mark_outline_width_px}
								cx={point.cx} cy={point.cy} r={storyChartGeometry.dot_radius_px}>
								<title>{point.label}: x {point.statedX} {drawing.xUnit ?? ''},
									y {point.statedY} {drawing.yUnit ?? ''}</title>
							</circle>
						{/each}
					{/if}
				{:else}
					<text class="column-label" text-anchor="middle" x={drawing.leftX} y={storyChartGeometry.slope_header_band_px / 2}>
						{drawing.leftLabel}
					</text>
					<text class="column-label" text-anchor="middle" x={drawing.rightX} y={storyChartGeometry.slope_header_band_px / 2}>
						{drawing.rightLabel}
					</text>
					{#each drawing.slopes as slope (slope.color)}
						<line
							class={`slope-line chart-${slope.color}`}
							x1={slope.left.x}
							y1={slope.left.y}
							x2={slope.right.x}
							y2={slope.right.y}
							stroke-width={slope.left.emphasized || slope.right.emphasized
								? storyChartGeometry.slope_highlight_line_width_px
								: storyChartGeometry.slope_line_width_px}
						/>
						<circle
							class={`slope-point chart-${slope.color}`}
							class:emphasized={slope.left.emphasized}
							stroke-width={storyChartGeometry.mark_outline_width_px}
							cx={slope.left.x}
							cy={slope.left.y}
							r={storyChartGeometry.dot_radius_px}
						/>
						<circle
							class={`slope-point chart-${slope.color}`}
							class:emphasized={slope.right.emphasized}
							stroke-width={storyChartGeometry.mark_outline_width_px}
							cx={slope.right.x}
							cy={slope.right.y}
							r={storyChartGeometry.dot_radius_px}
						/>
						<text class="figure" text-anchor="end" x={slope.left.x - storyChartGeometry.value_gap_px} y={slope.left.y}>
							{slope.left.displayed}
						</text>
						<text class="figure" x={slope.right.x + storyChartGeometry.value_gap_px} y={slope.right.y}>
							{slope.right.displayed}
						</text>
					{/each}
					{#if drawing.unit}
						<text class="unit" x="0" y={drawing.height - storyChartGeometry.slope_footer_band_px / 2}>
							{drawing.unit}
						</text>
					{/if}
				{/if}
			</svg>
			{#if drawing.type === 'bubble'}
				<div class="bubble-size-key px-3" aria-hidden="true">
					<span>Circle area represents {drawing.sizeUnit ?? 'size'}.</span>
					<span class="bubble-key-entry">
						<span class="bubble-key-mark"
							style={`width: ${drawing.sizeRange.minRadius * 2}px; height: ${drawing.sizeRange.minRadius * 2}px`}></span>
						<span>{drawing.sizeRange.min}{drawing.sizeUnit ? ` ${drawing.sizeUnit}` : ''}</span>
					</span>
					<span class="bubble-key-entry">
						<span class="bubble-key-mark"
							style={`width: ${drawing.maxRadius * 2}px; height: ${drawing.maxRadius * 2}px`}></span>
						<span>{drawing.sizeRange.max}{drawing.sizeUnit ? ` ${drawing.sizeUnit}` : ''}</span>
					</span>
				</div>
				<ul class="bubble-readings px-3 pb-3 text-xs leading-normal text-text-secondary">
					{#each drawing.points as point (point.label)}
						<li class:highlighted={point.emphasized}>
							<span class="font-semibold text-text">{point.label}</span>:
							x {point.displayedX}{drawing.xUnit ? ` ${drawing.xUnit}` : ''},
							y {point.displayedY}{drawing.yUnit ? ` ${drawing.yUnit}` : ''},
							area {point.displayedSize}{drawing.sizeUnit ? ` ${drawing.sizeUnit}` : ''}
						</li>
					{/each}
				</ul>
			{:else if drawing.type === 'scatter'}
				<ul class="scatter-readings px-3 pb-3 text-xs leading-normal text-text-secondary">
					{#each drawing.points as point (point.label)}
						<li class:highlighted={point.emphasized}>
							<span class="font-semibold text-text">{point.label}</span>:
							x {point.displayedX}{drawing.xUnit ? ` ${drawing.xUnit}` : ''},
							y {point.displayedY}{drawing.yUnit ? ` ${drawing.yUnit}` : ''}
						</li>
					{/each}
				</ul>
			{:else if drawing.type === 'slope'}
				<ul class="slope-legend px-3">
					{#each drawing.slopes as slope (slope.color)}
						<li>
							<span class={`legend-mark chart-${slope.color}`} aria-hidden="true"></span>
							<span>{slope.name}</span>
						</li>
					{/each}
				</ul>
			{:else if drawing.type === 'line' && drawing.lines.length > 1}
				<ul class="line-legend px-3">
					{#each drawing.lines as line (line.name)}
						<li>
							<svg class={`line-legend-mark chart-${line.color}`} viewBox="0 0 24 4" aria-hidden="true">
								<line
									x1="0"
									x2="24"
									y1="2"
									y2="2"
									stroke-dasharray={line.dasharray}
									stroke-width={storyChartGeometry.line_width_px}
								/>
							</svg>
							<span>{line.name}</span>
						</li>
					{/each}
				</ul>
			{/if}
			{/if}
			{#if drawing.caption}
				<figcaption class="px-3 pb-3 text-xs leading-normal text-text-secondary">{drawing.caption}</figcaption>
			{/if}
		{/if}
	</figure>
{:else if wanted && settled !== wanted}
	<!-- Where the drawing will go, and nothing a reader can see: no box, no
	     border, no height. It exists so the fetch can wait until the story is
	     nearly on screen, and a story whose marks never arrive keeps exactly the
	     height it has now. -->
	<div class="slot" use:askWhenNear></div>
{/if}

<style>
	/* The svg draws at the width it was measured in, so one drawn unit is one CSS
	   pixel and the `viewBox` scales nothing. `max-width` rather than `width` is
	   the guard: the measured room is floored to whole pixels so the drawing
	   already fits, and this only catches the frame between a card moving and the
	   watcher reporting it. A `width: 100%` here would stretch the coordinate
	   space again and undo the whole row. **The guard is one-sided.** A card that
	   narrowed clamps the old drawing down to fit; a card that widened leaves it
	   short until the redraw, because `max-width` stretches nothing. */
	.visual svg {
		display: block;
		height: auto;
		max-width: 100%;
	}

	/* Type on the card, read the way the reader note above it is read. The chart
	   ramp is for marks that carry no word, and a name and a figure both do.

	   `--text-xs` rather than a px size, for the reason every other type on the
	   site takes a token: a px size ignores a reader who set their browser text
	   larger. The drawing is placed at the card's own width, so the token keeps
	   its computed size rather than being scaled with a fixed viewBox. The
	   browser gate measures the rendered text against that same token. */
	.name,
	.figure,
	.unit {
		dominant-baseline: middle;
		fill: var(--color-text-secondary);
		font-family: inherit;
		font-size: var(--text-xs);
	}

	/* The figure a reader compares is the one thing on the drawing they read as a
	   number rather than as a label, so it takes the page's own ink. */
	.figure {
		fill: var(--color-text);
	}

	/* `--chart-axis` is the token every console chart already draws an axis with,
	   so there is one answer to "what colour is an axis here" rather than two. */
	.axis {
		stroke: var(--chart-axis);
	}

	.grid {
		stroke: var(--chart-grid);
		stroke-dasharray: var(--space-1);
	}

	.date-label {
		dominant-baseline: middle;
		fill: var(--color-text-secondary);
		font-family: inherit;
		font-size: var(--text-xs);
	}

	.bar {
		fill: var(--chart-1);
	}

	.bar.emphasized {
		fill: var(--chart-2);
		stroke: var(--color-text);
		stroke-dasharray: var(--space-1);
	}

	.name.emphasized {
		font-weight: var(--font-weight-semibold);
		fill: var(--color-text);
	}

	.dot {
		fill: var(--chart-1);
	}

	.scatter-point {
		fill: var(--chart-1);
		stroke: var(--color-surface);
	}

	.scatter-point.emphasized {
		fill: var(--chart-2);
		stroke: var(--color-text);
		stroke-dasharray: var(--space-1);
	}

	.bubble-point {
		fill: var(--chart-1);
		stroke: var(--color-surface);
	}

	.bubble-point.emphasized {
		fill: var(--chart-2);
		stroke: var(--color-text);
		stroke-dasharray: var(--space-1);
	}

	.bubble-size-key {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-2) var(--space-3);
		padding-bottom: var(--space-2);
		font-size: var(--text-xs);
		color: var(--color-text-secondary);
	}

	.bubble-key-entry {
		display: inline-flex;
		align-items: center;
		gap: var(--space-1);
	}

	.bubble-key-mark {
		display: inline-block;
		flex: none;
		border-radius: 50%;
		background: var(--chart-1);
	}

	.bubble-readings {
		list-style: none;
	}

	.bubble-readings .highlighted {
		font-weight: var(--font-weight-semibold);
		color: var(--color-text);
	}

	.scatter-readings {
		list-style: none;
	}

	.scatter-readings .highlighted {
		font-weight: var(--font-weight-semibold);
		color: var(--color-text);
	}

	.dot.emphasized,
	.slope-point.emphasized {
		fill: var(--chart-2);
		stroke: var(--color-text);
	}

	.series-line {
		fill: none;
		stroke-linecap: round;
		stroke-linejoin: round;
	}

	.line-point {
		fill: var(--color-surface);
	}

	.line-point.emphasized {
		fill: var(--chart-2);
		stroke: var(--color-text);
	}

	.column-label {
		dominant-baseline: middle;
		fill: var(--color-text);
		font-family: inherit;
		font-size: var(--text-xs);
		font-weight: var(--font-weight-semibold);
	}

	.slope-line {
		stroke-linecap: round;
	}

	.chart-1 { color: var(--chart-1); stroke: var(--chart-1); }
	.chart-2 { color: var(--chart-2); stroke: var(--chart-2); }
	.chart-3 { color: var(--chart-3); stroke: var(--chart-3); }
	.chart-4 { color: var(--chart-4); stroke: var(--chart-4); }
	.chart-5 { color: var(--chart-5); stroke: var(--chart-5); }
	.chart-6 { color: var(--chart-6); stroke: var(--chart-6); }
	.chart-7 { color: var(--chart-7); stroke: var(--chart-7); }
	.chart-8 { color: var(--chart-8); stroke: var(--chart-8); }

	.slope-point {
		fill: var(--color-surface);
	}

	.slope-legend {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2) var(--space-4);
		padding-bottom: var(--space-2);
		list-style: none;
	}

	.slope-legend li {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		font-size: var(--text-xs);
		color: var(--color-text-secondary);
	}

	.legend-mark {
		width: var(--space-4);
		border-top: 2px solid;
	}

	.line-legend {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2) var(--space-4);
		padding-bottom: var(--space-2);
		list-style: none;
	}

	.line-legend li {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		font-size: var(--text-xs);
		color: var(--color-text-secondary);
	}

	.line-legend-mark {
		width: var(--space-4);
		height: var(--space-1);
		overflow: visible;
	}

	/* Stated rather than left to an empty box, so nothing a later rule does to a
	   bare div can give this one a height a reader would see. */
	.slot {
		height: 0;
	}
</style>
