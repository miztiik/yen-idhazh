<script lang="ts">
	/** Keep route identity, navigation, evidence and one shared window beside the readings. */
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import ConsoleNav from '$lib/components/ConsoleNav.svelte';
	import WindowControl from '$lib/components/WindowControl.svelte';
	import WindowStatus from '$lib/components/WindowStatus.svelte';
	import ChartTooltip from '$lib/console/ChartTooltip.svelte';
	import BackToTop from '$lib/components/BackToTop.svelte';
	import Icon from '$lib/icons/Icon.svelte';
	import { ROUTE_GLYPHS } from '$lib/console/route-glyph';
	import { stripRoutes } from '$lib/console/band';
	import { consoleChromeOf } from '$lib/console/chrome';
	import { consoleHoverReadout, consoleKnobs, routeConsole } from '$lib/console/route-console';
	import { completenessOf, completenessSentence, untilNextUtcDay } from '$lib/console/completeness';
	import { provideWindowSlot, type WindowSource } from '$lib/console/window-slot';
	import { createWindowPreference } from '$lib/console/window-preference';
	import { provideNumberFormat } from '$lib/number-format-context';
	import { provideChartLabels, measureChartLabels } from '$lib/charts/label-context';
	import type { ChartLabels } from '$lib/charts/frame';
	import { shortDate, clockUtc } from '$lib/format';

	let { data, children } = $props();
	// svelte-ignore state_referenced_locally
	provideNumberFormat(data.number_format);
	const configured = consoleKnobs();
	const hoverEnabled = consoleHoverReadout();
	const routes = $derived(stripRoutes(data.routes));
	const route = $derived(routes.find((entry) => entry.href.replace(/\/$/, '') === page.route.id) ?? routes[0]);
	const active = $derived(route.id);
	const contents = $derived(routeConsole(active).panel_groups.filter((group) => group.title !== ''));
	const chrome = $derived(consoleChromeOf(page.data));
	const workbench = $derived(chrome === 'workbench');

	let chosen = $state(configured.default_window_days);
	const preference = createWindowPreference(configured.default_window_days, configured.window_presets, (days) => { chosen = days; });
	let handed = $state.raw<WindowSource | null>(null);
	provideWindowSlot((source) => { handed = source; }, {
		get days() { return chosen; },
		select: preference.select
	});
	const windowSource = $derived<WindowSource>(handed !== null && handed.route === active ? handed : {
		route: active, days: chosen, presets: configured.window_presets, busy: false, ready: false,
		statusLine: null, monthsFor: () => 0, onChange: preference.select
	});
	let labels = $state.raw<ChartLabels | null>(null);
	provideChartLabels(() => labels);

	let now = $state<number | null>(null);
	let heading = $state<HTMLHeadingElement | null>(null);
	let toolbar = $state<HTMLElement | null>(null);
	onMount(() => {
		if (toolbar === null) return;
		const node = toolbar;
		const root = document.documentElement;
		const previous = root.style.getPropertyValue('--console-toolbar-height');
		const measure = () => root.style.setProperty('--console-toolbar-height',
			`${getComputedStyle(node).position === 'sticky' ? node.getBoundingClientRect().height : 0}px`);
		const observer = new ResizeObserver(measure);
		observer.observe(node);
		measure();
		return () => {
			observer.disconnect();
			if (previous) root.style.setProperty('--console-toolbar-height', previous);
			else root.style.removeProperty('--console-toolbar-height');
		};
	});
	onMount(() => {
		preference.mount(() => window.localStorage);
		let timer: ReturnType<typeof setTimeout>;
		const look = () => {
			clearTimeout(timer);
			now = Date.now();
			timer = setTimeout(look, untilNextUtcDay(now) + 1000);
		};
		const shown = () => { if (document.visibilityState === 'visible') look(); };
		look();
		document.addEventListener('visibilitychange', shown);
		return () => { clearTimeout(timer); document.removeEventListener('visibilitychange', shown); };
	});
	const completeness = $derived(completenessOf(data.band.finishedAt, now, configured.completeness_grace_days));
</script>

<section class="console-shell" data-surface="operator" data-console-route={active} data-console-chrome={chrome}>
	<span class="console-label-measure" aria-hidden="true" use:measureChartLabels={(value) => { labels = value; }}>0123456789</span>
	<ConsoleNav {routes} {active} groups={contents} />
	<div class="console-main">
		<span id="console-top" class="console-top-anchor" aria-hidden="true"></span>
		<div class="console-toolbar" bind:this={toolbar}>
		<header class="console-route-head">
			<h1 id="console-route-title" tabindex="-1" bind:this={heading}>
				<span class="page-glyph" data-route-glyph={ROUTE_GLYPHS[active]}><Icon id={ROUTE_GLYPHS[active]} /></span>
				{route.label}
			</h1>
			{#if !workbench}
				<WindowControl days={windowSource.days} presets={windowSource.presets}
					busy={windowSource.busy} ready={windowSource.ready} onChange={windowSource.onChange} compact />
			{/if}
			<BackToTop {heading} />
		</header>
		{#if !workbench}
			<div class="console-window-evidence">
				<details class="console-data-dates" data-console-data-dates>
					<summary>Data dates (UTC)</summary>
					<div class="console-date-readings">
						{#if windowSource.record}<p>Native record</p>{/if}
						<WindowStatus days={windowSource.days} presets={windowSource.presets}
							monthsFor={windowSource.monthsFor} busy={windowSource.busy} ready={windowSource.ready}
							statusLine={windowSource.statusLine ?? null} record={windowSource.record ?? null} />
						{#if windowSource.publishedWindow}
							{@const span = windowSource.publishedWindow}
							<p data-private-window data-range-from={span.start} data-range-to={span.end}>
								Published days: {shortDate(span.start)}{span.start === span.end ? '' : ` - ${shortDate(span.end)}`} UTC.
							</p>
						{/if}
						{#if completeness.kind !== 'unread'}
							{@const finished = new Date(completeness.finished).toISOString()}
							<p>Last console update: <time datetime={finished}>{shortDate(finished.slice(0, 10))}, {clockUtc(finished)}</time>.</p>
						{/if}
					</div>
				</details>
			</div>
		{/if}
		</div>
		{#if !workbench}
			{#if completeness.kind !== 'complete'}
				<div class="console-evidence">
					<p class="console-completeness" data-console-completeness={completeness.kind}>{completenessSentence(completeness)}</p>
				</div>
			{/if}
			<noscript><p class="console-noscript" data-console-noscript>Published-record charts need JavaScript. Their headings and reserved frames remain below.</p></noscript>
		{/if}
		<div class="console-route-content">{@render children()}</div>
	</div>
	<ChartTooltip enabled={hoverEnabled} />
</section>

<style>
	.console-shell {
		display: grid;
		gap: var(--console-content-gap);
		padding-block: var(--console-panel-gap) var(--console-group-gap);
		font-family: var(--font-reading);
		font-size: var(--console-body-size);
		line-height: var(--console-body-leading);
		font-weight: var(--console-body-weight);
		letter-spacing: var(--console-body-tracking);
	}
	.console-main, .console-route-content { min-inline-size: 0; }
	.console-main, .console-route-content { isolation: isolate; }
	.console-top-anchor { display: block; block-size: 0; }
	.console-toolbar {
		position: sticky;
		inset-block-start: 0;
		z-index: 1;
		padding-block: var(--console-control-gap);
		border-block-end: 1px solid var(--color-rule);
		background: var(--color-bg);
	}
	[data-console-chrome='workbench'] .console-route-head { grid-template-columns: minmax(0, 1fr) auto; }
	.console-window-evidence { margin-block-start: var(--console-control-padding-block); }
	.console-data-dates {
		color: var(--color-text-secondary);
		font-size: var(--console-small-size);
		line-height: var(--console-small-leading);
	}
	.console-data-dates summary { cursor: pointer; width: fit-content; }
	.console-date-readings { display: grid; gap: var(--console-control-padding-block); padding-block-start: var(--console-control-gap); }
	.console-date-readings p { margin: 0; }
	.console-route-head {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto auto;
		align-items: center;
		justify-content: space-between;
		gap: var(--console-control-gap) var(--console-panel-gap);
	}
	h1 {
		display: flex;
		align-items: center;
		gap: var(--console-control-gap);
		margin: 0;
		font-family: var(--font-display);
		font-size: var(--console-page-title-size);
		line-height: var(--console-page-title-leading);
		font-weight: var(--console-page-title-weight);
		letter-spacing: var(--console-page-title-tracking);
	}
	.page-glyph { display: flex; flex: none; inline-size: var(--console-page-title-leading); block-size: var(--console-page-title-leading); color: var(--color-accent); }
	.page-glyph :global(svg) { inline-size: 100%; block-size: 100%; }
	.console-evidence {
		display: grid;
		gap: var(--console-control-padding-block);
		margin-block: var(--console-control-gap) var(--console-panel-gap);
	}
	.console-completeness, .console-noscript {
		margin: 0;
		color: var(--color-text-secondary);
		font-size: var(--console-small-size);
		line-height: var(--console-small-leading);
	}
	.console-noscript { padding-block: var(--console-panel-gap); }
	.console-label-measure {
		position: absolute;
		visibility: hidden;
		pointer-events: none;
		inline-size: max-content;
		font-family: var(--font-data);
		font-size: var(--console-small-size);
		line-height: var(--console-small-leading);
		font-weight: var(--console-small-weight);
		letter-spacing: var(--console-small-tracking);
	}
	@media (max-width: 1023px) {
		.console-shell { gap: var(--console-control-gap); padding-block-start: var(--console-control-gap); }
		.console-evidence {
			gap: 0;
			margin-block: var(--console-control-padding-block);
		}
		@media (max-width: 639px) {
			h1 { font-size: var(--console-panel-title-size); line-height: var(--console-panel-title-leading); }
			.page-glyph { inline-size: var(--console-panel-title-leading); block-size: var(--console-panel-title-leading); }
		}
	}
	@media (min-width: 1024px) {
		.console-shell { grid-template-columns: var(--console-rail-width) minmax(0, 1fr); align-items: start; }
		.console-shell[data-console-chrome='workbench'] { flex: 1 1 0; min-block-size: min-content; align-items: stretch; }
		[data-console-chrome='workbench'] .console-main { display: flex; flex-direction: column; min-block-size: min-content; }
		[data-console-chrome='workbench'] .console-toolbar { position: static; border: 0; }
		[data-console-chrome='workbench'] .console-route-content { display: flex; flex-direction: column; flex: 1 1 0; min-block-size: min-content; }
		[data-console-chrome='workbench'] .console-route-head { padding-block-end: var(--console-control-gap); }
	}
</style>
