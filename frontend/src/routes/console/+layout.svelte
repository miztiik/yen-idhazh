<script lang="ts">
	/** Keep route identity, navigation, evidence and one shared window beside the readings. */
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import ConsoleBand from '$lib/components/ConsoleBand.svelte';
	import ConsoleNav from '$lib/components/ConsoleNav.svelte';
	import WindowControl from '$lib/components/WindowControl.svelte';
	import WindowStatus from '$lib/components/WindowStatus.svelte';
	import { stripRoutes } from '$lib/console/band';
	import { consoleChromeOf } from '$lib/console/chrome';
	import { consoleKnobs, routeConsole } from '$lib/console/route-console';
	import { completenessOf, completenessSentence, untilNextUtcDay } from '$lib/console/completeness';
	import { provideWindowSlot, type WindowSource } from '$lib/console/window-slot';
	import { createWindowPreference } from '$lib/console/window-preference';
	import { provideNumberFormat } from '$lib/number-format-context';
	import { provideChartLabels, measureChartLabels } from '$lib/charts/label-context';
	import type { ChartLabels } from '$lib/charts/frame';

	let { data, children } = $props();
	// svelte-ignore state_referenced_locally
	provideNumberFormat(data.number_format);
	const configured = consoleKnobs();
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
	const windowSource = $derived<WindowSource>(handed ?? {
		days: chosen, presets: configured.window_presets, busy: false, ready: false,
		statusLine: null, monthsFor: () => 0, onChange: preference.select
	});
	let labels = $state.raw<ChartLabels | null>(null);
	provideChartLabels(() => labels);

	let now = $state<number | null>(null);
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
	<ConsoleNav {routes} {active} groups={contents} worst={data.band.worst?.id ?? null} />
	<div class="console-main">
		<header class="console-route-head">
			<h1 id="console-top">{route.label}</h1>
			{#if !workbench}
				<WindowControl days={windowSource.days} presets={windowSource.presets}
					busy={windowSource.busy} ready={windowSource.ready} onChange={windowSource.onChange} />
			{/if}
		</header>
		{#if !workbench}
			<div class="console-evidence">
				<WindowStatus days={windowSource.days} presets={windowSource.presets}
					monthsFor={windowSource.monthsFor} busy={windowSource.busy} ready={windowSource.ready}
					statusLine={windowSource.statusLine ?? null} record={windowSource.record ?? null} />
				{#if completeness !== null}
					<p class="console-completeness" data-console-completeness={completeness.kind}>{completenessSentence(completeness)}</p>
				{/if}
			</div>
			<ConsoleBand band={data.band} />
			<noscript><p class="console-noscript" data-console-noscript>Published-record charts need JavaScript. Their headings and reserved frames remain below.</p></noscript>
		{/if}
		<div class="console-route-content">{@render children()}</div>
	</div>
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
	.console-route-head {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--console-control-gap) var(--console-panel-gap);
	}
	h1 {
		margin: 0;
		font-family: var(--font-display);
		font-size: var(--console-page-title-size);
		line-height: var(--console-page-title-leading);
		font-weight: var(--console-page-title-weight);
		letter-spacing: var(--console-page-title-tracking);
	}
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
	}
	@media (min-width: 1024px) {
		.console-shell { grid-template-columns: var(--console-rail-width) minmax(0, 1fr); align-items: start; }
		.console-shell[data-console-chrome='workbench'] { flex: 1 1 0; min-block-size: 0; align-items: stretch; }
		[data-console-chrome='workbench'] .console-main { display: flex; flex-direction: column; min-block-size: 0; }
		[data-console-chrome='workbench'] .console-route-content { display: flex; flex-direction: column; flex: 1 1 0; min-block-size: 0; }
		[data-console-chrome='workbench'] .console-route-head { padding-block-end: var(--console-control-gap); }
	}
</style>
