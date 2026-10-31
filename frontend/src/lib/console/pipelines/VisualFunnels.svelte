<script lang="ts">
	import { pipelineFunnels, downgradeFunnels, type AttemptCount, type ClassFunnel } from './visual-funnels';
	import type { AttemptRead } from './attempt-notes';
	let { counts, read, notes, kind }: { counts: AttemptCount[]; read: AttemptRead; notes: string[]; kind: 'pipeline' | 'downgrade' } = $props();
	const funnels = $derived<ClassFunnel[]>((kind === 'pipeline' ? pipelineFunnels(counts) : downgradeFunnels(counts))
		.filter((funnel) => funnel.denominator > 0));
	const basis = $derived(kind === 'pipeline'
		? 'Every share is of the attempts in the same potential class.'
		: 'Every share is of the drafted plans in the same potential class.');
</script>
<p data-comparison={basis}>{basis}</p>
{#each notes as note}<p data-record-note>{note}</p>{/each}
{#if read === 'read' && funnels.length === 0}<p data-empty="quiet">No visual attempt is recorded in this window.</p>{/if}
{#each funnels as funnel (funnel.group)}
	<section data-funnel={kind} data-funnel-class={funnel.group} aria-label="{funnel.group}, {funnel.denominator} {kind === 'pipeline' ? 'attempts' : 'drafted plans'}">
		<h4>{funnel.group} <span>{funnel.denominator}</span></h4>
		<ol>
			{#each funnel.steps as step (step.label)}
				<li data-funnel-step={step.label} data-count={step.count} data-grew={step.grew ? '' : undefined}>
					<span class="name">{step.label}</span>
					<span class="bar" style:inline-size="{step.share ?? 0}%"></span>
					<span class="figure">{step.count}{step.share === null ? '' : ` (${step.share}%)`}</span>
					{#if step.grew}<span data-funnel-grew>more than the stage before</span>{/if}
				</li>
			{/each}
		</ol>
		{#if funnel.ends.length > 0}
			<ul>
				{#each funnel.ends as end (end.label)}
					<li data-funnel-end={end.label} data-count={end.count}>{end.label}: {end.count}{end.share === null ? '' : ` (${end.share}%)`}</li>
				{/each}
			</ul>
			{#if funnel.unaccounted !== 0}<p data-funnel-unaccounted={funnel.unaccounted}>{funnel.unaccounted} plans are not accounted for by these ends.</p>{/if}
		{/if}
		{#if funnel.losses.length > 0}
			<ul data-funnel-losses>
				{#each funnel.losses as loss (loss.label)}<li data-funnel-loss={loss.label} data-count={loss.count}>Stopped, {loss.label}: {loss.count}</li>{/each}
			</ul>
		{/if}
	</section>
{/each}
<style>
	section { margin-block-start: var(--space-5); }
	h4 span { font-weight: normal; color: var(--color-text-muted); }
	ol, ul { list-style: none; padding: 0; margin: 0; font-size: var(--text-sm); }
	li { display: grid; grid-template-columns: 11rem 1fr auto; gap: var(--space-3); align-items: center; }
	ul li { display: block; }
	.bar { block-size: 0.75rem; background: var(--chart-1); border-radius: var(--radius-sm); min-inline-size: 1px; max-inline-size: 100%; }
	.figure { font-variant-numeric: tabular-nums; }
	[data-funnel-grew] { grid-column: 1 / -1; font-style: italic; }
	[data-grew] .bar { background: var(--chart-3); }
</style>
