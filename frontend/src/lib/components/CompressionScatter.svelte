<script lang="ts">
	import 'uplot/dist/uPlot.min.css';
	import { onDestroy, onMount } from 'svelte';
	import { rowsInWindow, type CompressionPoint, type SummaryBand } from '$lib/charts/series';
	import type { TimeWindow } from '$lib/charts/viewport';

	let {
		points,
		viewport,
		bands,
		height
	}: {
		points: CompressionPoint[];
		viewport: TimeWindow;
		bands: SummaryBand[];
		height: number;
	} = $props();

	let host: HTMLDivElement;
	let plot: { destroy: () => void } | null = null;
	let ready = $state(false);
	const visible = $derived(rowsInWindow(points, viewport));
	const maxSource = $derived(Math.max(100, ...visible.map((point) => point.source_words)));
	const maxSummary = $derived(Math.max(100, ...visible.map((point) => point.summary_words), ...bands.map((band) => band.target_words_max)));

	function x(value: number): number {
		const min = Math.log10(1);
		const max = Math.log10(maxSource);
		return ((Math.log10(Math.max(1, value)) - min) / Math.max(1, max - min)) * 360;
	}

	function y(value: number): number {
		return height - (value / maxSummary) * height;
	}

	function bandFor(sourceWords: number): SummaryBand {
		return bands.reduce((chosen, band) => (sourceWords >= band.min_source_words ? band : chosen), bands[0]);
	}

	function token(name: string, fallback: string): string {
		if (typeof window === 'undefined') return fallback;
		const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
		return value || fallback;
	}

	async function drawUplot() {
		if (!host) return;
		const [{ default: uPlot }] = await Promise.all([import('uplot')]);
		plot?.destroy();
		const sorted = [...visible].sort((a, b) => a.source_words - b.source_words);
		const ink = token('--color-text', '#16181d');
		const rule = token('--color-rule', '#e5e3df');
		const accent = token('--color-accent', '#0b5cd5');
		plot = new uPlot(
			{
				width: host.clientWidth || 360,
				height,
				scales: { x: { time: false } },
				axes: [
					{ stroke: ink, grid: { stroke: rule } },
					{ stroke: ink, grid: { stroke: rule } }
				],
				series: [
					{},
					{
						label: 'summary words',
						stroke: accent,
						fill: accent,
						points: { show: true, size: 6 }
					}
				]
			},
			[sorted.map((point) => point.source_words), sorted.map((point) => point.summary_words)],
			host
		);
	}

	onMount(() => {
		ready = true;
		void drawUplot();
		const observer = new MutationObserver(() => void drawUplot());
		observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
		const resize = () => void drawUplot();
		globalThis.window.addEventListener('resize', resize);
		return () => {
			observer.disconnect();
			globalThis.window.removeEventListener('resize', resize);
		};
	});

	$effect(() => {
		if (ready) void drawUplot();
	});

	onDestroy(() => {
		plot?.destroy();
	});
</script>

<section class="mt-8">
	<h2 class="text-[1.0625rem] font-semibold text-text">Compression</h2>
	<p class="mt-1 text-[0.8125rem] text-text-tertiary">
		Source words use a log x axis. Diamonds mark summaries that carried the truncation flag.
	</p>
	<div class="mt-4 rounded-md border border-rule bg-surface p-3" data-compression>
		<svg
			class="w-full overflow-visible"
			height={height + 34}
			viewBox={`0 0 360 ${height + 34}`}
			role="img"
			aria-label="Source words against summary words"
		>
			<line x1="0" x2="360" y1={height} y2={height} stroke="var(--color-rule)" />
			<line x1="0" x2="0" y1="0" y2={height} stroke="var(--color-rule)" />
			{#if visible.length === 0}
				<line
					x1="0"
					x2="360"
					y1={height / 2}
					y2={height / 2}
					stroke="var(--color-text-tertiary)"
					stroke-dasharray="4 4"
				/>
				<text x="8" y={height / 2 - 8} fill="var(--color-text-tertiary)" font-size="12">
					No scored items in this window
				</text>
			{:else}
				{#each visible as point (`${point.date}-${point.item_id}`)}
					{@const band = bandFor(point.source_words)}
					<line
						x1={x(point.source_words)}
						x2={x(point.source_words)}
						y1={y(band.target_words_min)}
						y2={y(band.target_words_max)}
						stroke="var(--color-accent)"
						stroke-opacity="0.35"
					/>
					{#if point.truncation_flagged}
						<rect
							x={x(point.source_words) - 4}
							y={y(point.summary_words) - 4}
							width="8"
							height="8"
							transform={`rotate(45 ${x(point.source_words)} ${y(point.summary_words)})`}
							fill="var(--band-low)"
						>
							<title>{point.date} {point.item_id}: {point.summary_words} of {point.source_words}</title>
						</rect>
					{:else}
						<circle
							cx={x(point.source_words)}
							cy={y(point.summary_words)}
							r="4"
							fill="var(--color-text)"
						>
							<title>{point.date} {point.item_id}: {point.summary_words} of {point.source_words}</title>
						</circle>
					{/if}
				{/each}
			{/if}
			<text x="0" y={height + 24} fill="var(--color-text-tertiary)" font-size="11">
				source words
			</text>
			<text x="282" y={height + 24} fill="var(--color-text-tertiary)" font-size="11">
				summary words
			</text>
		</svg>
		<div class="mt-4" bind:this={host} aria-hidden="true"></div>
	</div>
</section>
