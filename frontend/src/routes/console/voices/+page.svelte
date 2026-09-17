<script lang="ts">
	/** Who supplied the day, and what the ranking makes of them.
	 *
	 * Four panels moved here off `/console/` on 2026-09-14 and Pipelines kept
	 * none of them: which sources we may ask, what the ranking makes of each
	 * feed, which feeds broke, and what the truncation cap cost each source.
	 * They answer one question, and a reader asking which feed is broken should
	 * not have to know that half the answer was filed under "did the runs work".
	 *
	 * Two of the four follow the window control; two do not and each says so.
	 * The ranking weight is one of the two: it was reduced over
	 * `collect.reliability_window_days` when the run happened, so a control that
	 * moved it would be a control that lies.
	 */
	import { base } from '$app/paths';
	import { onMount } from 'svelte';
	import { axisLabels, denseCellFor, ROW_STRIP_PX, type LabelAlign } from '$lib/charts/run-history';
	import { grouped } from '$lib/charts/series';
	import { windowOfDays } from '$lib/charts/viewport';
	import { shortDate } from '$lib/format';
	import SourceCutRange from '$lib/components/SourceCutRange.svelte';
	import TargetBar from '$lib/components/TargetBar.svelte';
	import WindowControl from '$lib/components/WindowControl.svelte';
	import type { FeedDayOutcome, YieldDay } from './+page.server';

	let { data } = $props();

	const standing = $derived(data.standing);
	const pct = (share: number) => `${Math.round(share * 100)}%`;

	/** The same key the other four console routes read, so the operator's choice
	 * of span follows him between them rather than resetting on every click. */
	const WINDOW_KEY = 'idhazh:console-window';

	const presets = $derived(data.console.window_presets);

	// svelte-ignore state_referenced_locally
	let windowDays = $state(data.console.default_window_days);
	/** False until a browser has run this page. The control cannot do anything
	 * before that, so it says so rather than pretending. */
	let ready = $state(false);

	onMount(() => {
		ready = true;
		if (typeof localStorage === 'undefined') return;
		const stored = Number(localStorage.getItem(WINDOW_KEY));
		if (presets.includes(stored) && stored !== windowDays) show(stored);
	});

	function show(days: number, remember = true) {
		windowDays = days;
		if (remember && typeof localStorage !== 'undefined') {
			localStorage.setItem(WINDOW_KEY, String(days));
		}
	}

	/** Nothing on this route is fetched. Every span it can draw is already
	 * inlined, so no preset costs a month file and none of them is priced. */
	function monthsFor(): number {
		return 0;
	}

	/** The span the control is holding, always ending on the newest day the
	 * ledger carries. There is no pan here and there was none on the panels
	 * before they moved: the source table was reduced once per preset on the
	 * server, and the browser has no ledger to re-reduce a panned span from. */
	const viewport = $derived(
		windowOfDays(data.feedDates, data.today, windowDays, data.console.today_anchor)
	);
	const inWindow = $derived((date: string) => date >= viewport.start && date <= viewport.end);

	/** The source table for the window in force. One was built per preset at
	 * build time, so changing the window costs no fetch and no ledger read. */
	const cuts = $derived(
		data.sourceCutsByWindow.find((table) => table.days === windowDays) ??
			data.sourceCutsByWindow[0]
	);

	/** The days every feed strip is drawn over. One axis for the whole list, so
	 * two feeds can be read against each other: a feed broken since Tuesday and a
	 * feed flaky all month draw the same picture on two different axes. */
	const stripDates = $derived(data.feedDates.filter(inWindow));
	/** Fixed rather than measured. Twenty strips each watching their own width is
	 * twenty observers, and the room a list row has is a layout decision the
	 * server can make as well as the browser can. */
	const stripCell = $derived(denseCellFor(ROW_STRIP_PX, stripDates.length));
	const stripAxis = $derived(
		axisLabels(stripDates, {
			density: data.chart.tick_density,
			pitch: stripCell.cell + stripCell.gap
		})
	);
	const strips = $derived(
		new Map(
			data.feeds.map((feed) => [feed.feedId, new Map(feed.days.map((day) => [day.date, day]))])
		)
	);

	/** Is the record deep enough for "did not fail" to mean anything?
	 *
	 * Two runs deep it means "did not fail twice". The bar is the same knob the
	 * console prints a rate on everywhere else, because there is one question
	 * here - how thin is too thin a denominator - and a second number would be a
	 * second answer to it.
	 */
	const feedRecordReadable = $derived(data.feedRecord.runs >= data.console.min_attempts_for_rate);

	/** What a square means, in words. Colour is one signal and never the only
	 * one, and the two that are not a verdict take no band colour at all. */
	const FEED_KEY: { outcome: FeedDayOutcome; text: string }[] = [
		{ outcome: 'answered', text: 'answered' },
		{ outcome: 'failed', text: 'failed, or answered with nothing' },
		{ outcome: 'refused', text: 'politely refused' },
		{ outcome: 'resting', text: 'not asked - resting' }
	];

	/** The dwell strip's own geometry. Its axis is the run's, not the window
	 * control's: the countdown is counted against a knob the run applied, so a
	 * control that moved this span would move a number nothing else moved. */
	const dwellDates = $derived(data.retiring?.dates ?? []);
	const dwellCell = $derived(denseCellFor(ROW_STRIP_PX, dwellDates.length));
	const dwellAxis = $derived(
		axisLabels(dwellDates, {
			density: data.chart.tick_density,
			pitch: dwellCell.cell + dwellCell.gap
		})
	);

	/** What a square on the reliability strip means, in words. The two that are a
	 * verdict take the fill ramp; the one that is not takes no verdict colour. */
	const YIELD_KEY: { state: YieldDay; text: string }[] = [
		{ state: 'at-or-above', text: 'at or above the mark' },
		{ state: 'under', text: 'under the mark' },
		{ state: 'nothing', text: 'it decided nothing that day' }
	];

	/** A label is placed inside its column, not laid out by it, so the widest
	 * date on the axis cannot push a single day track out of step. */
	const ANCHOR: Record<LabelAlign, string> = {
		start: 'left: 0',
		centre: 'left: 50%; transform: translateX(-50%)',
		end: 'right: 0'
	};
</script>

<div data-console-panels="voices">
	<!-- The title, the strip and the band are the shell and live in
	     `../+layout.svelte`. The control stays here because it governs this
	     route's panels and nothing above them. -->
	<WindowControl days={windowDays} {presets} {monthsFor} {ready} onChange={show} />

	<p class="console-carry" data-console-carry="pipelines">
		{data.carries.voices}
		<a class="carry-link" href="{base}/console/">Pipelines &rarr;</a>
	</p>

	<h2 class="console-h2">Sources we may ask, and what they yield</h2>

	{#if data.sourceHealth === null}
		<p class="mt-2 text-[0.9375rem] text-text-secondary" data-source-health="absent">
			No run has published a source census yet, so there is nothing to draw here. It fills on the
			next run that publishes a day.
		</p>
	{:else}
		<p
			class="mt-2 text-[0.9375rem] text-text"
			data-source-health-lead
			data-source-health-sources={data.sourceHealth.sources}
			data-source-health-withheld={data.sourceHealth.withheld}
		>
			{data.sourceHealth.sources} sources sit on the desks that publish, and {data.sourceHealth
				.withheld}
			{data.sourceHealth.withheld === 1 ? 'of them is' : 'of them are'} held back right now.
		</p>

		<p class="mt-1 text-[0.8125rem] text-text-tertiary" data-window-exempt="source-health">
			Four separate facts, and none of them is averaged into the others: whether the site's own
			rules let us ask, whether the address is answering, whether a run has stopped asking it for
			good, and what it has published. A single score across the four would tell you something is
			wrong and nothing about what to do. The run decides all four from the private record and
			publishes them here, so this section renders a decision rather than making a second one.
			None of it follows the window control above - permission, answering and retirement come from
			the run's own reading of the ledger, and the publishing record has a fixed span of its own.
			This counts only the addresses a curator has left active, so it is a smaller list than the
			feeds below, which read every feed the ledger carried in the runs they report.
		</p>

		<div class="console-table mt-3" data-source-health="states">
			<table class="w-full text-[0.8125rem]">
				<thead class="text-text-tertiary">
					<tr class="border-b border-rule">
						<th class="py-2 text-start font-normal">Fact</th>
						<th class="py-2 text-start font-normal">State</th>
						<th class="py-2 text-end font-normal">Sources</th>
						<th class="py-2 text-start font-normal">What it withholds</th>
					</tr>
				</thead>
				<tbody>
					{#each data.sourceHealth.permission as fact (fact.id)}
						<tr class="border-b border-rule" data-source-state="permission-{fact.id}">
							<td class="py-2">Permission</td>
							<td class="py-2">{fact.label}</td>
							<td class="py-2 text-end tabular-nums" data-source-state-count>{fact.count}</td>
							<td class="py-2 text-text-secondary">{fact.withheld ?? 'nothing'}</td>
						</tr>
					{/each}
					{#each data.sourceHealth.availability as fact (fact.id)}
						<tr class="border-b border-rule" data-source-state="availability-{fact.id}">
							<td class="py-2">Reading</td>
							<td class="py-2">{fact.label}</td>
							<td class="py-2 text-end tabular-nums" data-source-state-count>{fact.count}</td>
							<td class="py-2 text-text-secondary">{fact.withheld ?? 'nothing'}</td>
						</tr>
					{/each}
					<tr class="border-b border-rule" data-source-state="retirement-retired">
						<td class="py-2">Retirement</td>
						<td class="py-2">the server said the address is gone</td>
						<td class="py-2 text-end tabular-nums" data-source-state-count
							>{data.sourceHealth.retired}</td
						>
						<td class="py-2 text-text-secondary"
							>no run asks this address again until its configured address changes</td
						>
					</tr>
				</tbody>
			</table>
		</div>

		{#if data.sourceHealth.notes.length === 0}
			<p class="mt-3 text-[0.9375rem] text-text-secondary" data-source-health="clear">
				Every source is allowed to be asked and answering, so there is nothing to name.
			</p>
		{:else}
			<div
				class="console-table mt-3"
				data-source-health="notes"
				data-source-health-drawn={data.sourceHealth.notes.length}
			>
				<p class="feeds-note">
					The sources held back, loudest state first. Retirement and a refusal come before a rest,
					because a rest lifts itself and neither of those does. The two counts span the same
					complete days as the record below, and a dash means the source was offered nothing in
					that span.
				</p>
				<table class="w-full text-[0.8125rem]">
					<thead class="text-text-tertiary">
						<tr class="border-b border-rule">
							<th class="py-2 text-start font-normal">Source</th>
							<th class="py-2 text-start font-normal">Desk</th>
							<th class="py-2 text-start font-normal">What is holding it back</th>
							<th class="py-2 text-end font-normal">Offered</th>
							<th class="py-2 text-end font-normal">Published</th>
						</tr>
					</thead>
					<tbody>
						{#each data.sourceHealth.notes as note (note.sourceId)}
							<tr class="border-b border-rule" data-source-note={note.sourceId}>
								<td class="py-2"
									>{note.title}<span class="source-note-id" data-source-note-id>{note.sourceId}</span
									></td
								>
								<td class="py-2 text-text-secondary">{note.vertical}</td>
								<td class="py-2 text-text-secondary" data-source-note-withheld>{note.withheld}</td>
								<td class="py-2 text-end tabular-nums"
									>{note.opportunities === 0 ? '-' : grouped(note.opportunities)}</td
								>
								<td class="py-2 text-end tabular-nums"
									>{note.opportunities === 0 ? '-' : grouped(note.publications)}</td
								>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>

			{#if data.sourceHealth.hidden > 0}
				<p class="mt-3 text-[0.8125rem] text-text-tertiary" data-source-health-more>
					{data.sourceHealth.hidden} more {data.sourceHealth.hidden === 1 ? 'source is' : 'sources are'}
					held back, none by a louder state than the last row here.
				</p>
			{/if}
		{/if}

		<p
			class="mt-3 text-[0.9375rem] text-text"
			data-source-health-record={data.sourceHealth.record.readable ? 'measured' : 'short'}
			data-source-health-days={data.sourceHealth.record.completeDates}
		>
			{#if data.sourceHealth.record.completeDates === 0}
				No day has finished with a planned article on it, so there is no publishing record yet.
			{:else}
				Over {data.sourceHealth.record.completeDates}
				complete {data.sourceHealth.record.completeDates === 1 ? 'day' : 'days'}, {data
					.sourceHealth.record.firstDate} to {data.sourceHealth.record.lastDate}, these sources
				were offered {grouped(data.sourceHealth.record.opportunities)} addresses and published {grouped(
					data.sourceHealth.record.publications
				)}. {grouped(data.sourceHealth.record.sourceFailures)}
				of those addresses were lost to a failure the source itself owns.
				{#if !data.sourceHealth.record.readable}
					The record is under the {data.sourceHealth.record.minCompleteDays} complete days a yield
					judgement needs, so these are counts and not a rate.
				{/if}
			{/if}
		</p>

		<p class="mt-1 text-[0.8125rem] text-text-tertiary" data-source-health-basis>
			An offer is one address planned on a day that has finished, counted once however many runs of
			that day tried it. Today is never counted: the run is still working, so its addresses have
			not all been attempted. A lost address is reported beside the two counts and never subtracted
			from either, so one lost article is counted once.
		</p>
	{/if}

	<h2 class="console-h2">What the ranking makes of each feed</h2>

	{#if standing === null}
		<div class="console-panel" data-console-empty="voices">
			<p class="empty-lead">No run has published a ranking weight yet.</p>
			<p class="empty-note">
				This panel draws one file, <code>source-health.json</code>, which the pipeline writes at
				the end of a run. It fills on the next run that writes a weight into it. Until then there
				is nothing to draw here, which is not the same as every feed being fine - the census
				above and the failure list below are read from the same file and are drawn already.
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

			<p class="note" data-voices-basis data-window-exempt="reliability">
				Published by run {standing.runId} at {standing.generatedAt}. The weight is the one that run
				applied, read from the record rather than worked out again here - which is why it does not
				follow the window control above. The run reduced it over {standing.windowDays} days when it
				ran, and a control that redrew it over seven would print a number no run ever applied.
			</p>
		</div>
	{/if}

	<h2 class="console-h2">Feeds that failed</h2>

	{#if data.feedRecord.runs === 0}
		<p class="mt-2 text-[0.9375rem] text-text-secondary" data-feeds="empty">
			No feed result has been recorded yet. The ledger fills as runs collect.
		</p>
	{:else}
		<p
			class="mt-2 text-[0.9375rem] text-text"
			data-feed-reliability={feedRecordReadable ? 'measured' : 'shallow'}
			data-feed-clean={data.feedRecord.clean.length}
			data-feed-checked={data.feedRecord.checked}
			data-feed-ineligible={data.feedRecord.ineligible.length}
			data-feed-runs={data.feedRecord.runs}
		>
			{#if feedRecordReadable}
				{data.feedRecord.clean.length} of {data.feedRecord.checked} feeds did not fail a read in these
				{data.feedRecord.runs}
				{data.feedRecord.runs === 1 ? 'run' : 'runs'}.
			{:else}
				{data.feedRecord.clean.length} of {data.feedRecord.checked} feeds did not fail a read.
				The record is {data.feedRecord.runs}
				{data.feedRecord.runs === 1 ? 'run' : 'runs'} deep, under the {data.console
					.min_attempts_for_rate} this page prints a rate on, so it is too early to read that as reliability.
			{/if}
			{#if data.feedRecord.ineligible.length > 0}
				{data.feedRecord.ineligible.length} more {data.feedRecord.ineligible.length === 1
					? 'feed was'
					: 'feeds were'} not read in these {data.feedRecord.runs}
				{data.feedRecord.runs === 1 ? 'run' : 'runs'} - a rest or the site's own rules held
				{data.feedRecord.ineligible.length === 1 ? 'it' : 'them'} back on every one - so
				{data.feedRecord.ineligible.length === 1 ? 'it is' : 'they are'} in neither count.
			{/if}
		</p>

		{#if data.feedRecord.ineligible.length > 0}
			<details class="console-disclosure mt-2" data-feed-ineligible-list>
				<summary class="console-summary" data-feed-ineligible-toggle>
					Name the {data.feedRecord.ineligible.length} the pipeline did not read
				</summary>
				<p class="mt-2 text-[0.8125rem] text-text-tertiary" data-feed-ineligible-note>
					A source honouring its own <code>robots.txt</code> has not failed, and neither has one the
					pipeline was resting. Neither has delivered anything either, so counting them among the
					feeds that did not fail reported a source we did not read as a reliable one.
				</p>
				<ul class="feed-clean-names" data-feed-ineligible-names>
					{#each data.feedRecord.ineligible as feedId (feedId)}
						<li data-feed-ineligible-name={feedId}>{feedId}</li>
					{/each}
				</ul>
			</details>
		{/if}

		{#if data.feedRecord.clean.length > 0}
			<details class="console-disclosure mt-2" data-feed-clean-list>
				<summary class="console-summary" data-feed-clean-toggle>
					Name the {data.feedRecord.clean.length} that did not fail
				</summary>
				<p class="mt-2 text-[0.8125rem] text-text-tertiary" data-feed-clean-note>
					Alphabetical, because there is no order here: a feed is read once a run, so every clean
					feed has the same record. A source whose <code>robots.txt</code> says no has not failed
					either.
				</p>
				<ul class="feed-clean-names" data-feed-clean-names>
					{#each data.feedRecord.clean as feedId (feedId)}
						<li data-feed-clean-name={feedId}>{feedId}</li>
					{/each}
				</ul>
			</details>
		{/if}
	{/if}

	<p class="mt-3 text-[0.8125rem] text-text-tertiary" data-window-exempt="feeds">
		The pipeline rests a feed after {data.quarantineAfter} failures in a row. The count beside
		each feed is that run of failures, read over these {data.feedRecord.runs}
		{data.feedRecord.runs === 1 ? 'run' : 'runs'} - it does not follow the window above, because
		the pipeline rests on an unbroken run of failures and not on a windowed count. The count
		above it is read over those same runs, for the same reason. The strip of days
		beside each feed does follow the window. A feed that answered with nothing counts as a
		failure: an empty answer costs the digest the same articles a refusal does. A source whose
		<code>robots.txt</code> says no does not, and a feed nobody has asked is in neither count.
	</p>

	{#if data.feedRecord.runs > 0 && data.feeds.length === 0}
		<p class="mt-4 text-[0.9375rem] text-text-secondary" data-feeds="clean">
			No feed has failed in these {data.feedRecord.runs}
			{data.feedRecord.runs === 1 ? 'run' : 'runs'}, so there is nothing to list.
		</p>
	{:else if data.feeds.length > 0}
		<div
			class="console-table mt-3"
			data-windowed="feed-outcomes"
			data-window-days={windowDays}
			data-model-rule="no"
			data-model-rule-name="feed-outcomes"
			data-model-rule-none="a feed answered or it did not, before any summary was written"
		>
			<p class="feeds-note">
				Nearest to a rest first, then by how much has gone wrong in total. Each strip is one
				square a day, oldest to newest, over these {windowDays} days.
			</p>

			<ol class="feed-rows" data-feeds="table" data-feeds-drawn={data.feeds.length} data-feeds-hidden={data.feedsHidden}>
				{#each data.feeds as feed (feed.feedId)}
					<!-- The streak and the track length are published because they are what
					     the marker is drawn from. A check that re-reads the bar's own
					     numbers off the page cannot be fooled by a bar drawn to the wrong
					     scale, which is the failure worth catching here: nothing about it
					     looks broken. -->
					<li
						class="feed-row"
						data-feed={feed.feedId}
						data-feed-resting={feed.resting ? 'yes' : null}
						data-feed-streak={feed.streak}
						data-feed-failures={feed.failures}
						data-feed-track={feed.marks.track}
					>
						<p class="feed-name">
							<span>{feed.feedId}</span>
							{#if feed.resting}
								<span class="feed-rested" data-rested>rested</span>
							{/if}
						</p>

						<div class="feed-bar" data-feed-cell="bar">
							<TargetBar
								marks={feed.marks}
								label="Failures in a row"
								valueText={feed.streak === 1 ? '1 failure' : `${feed.streak} failures`}
								targetText="rested at {data.quarantineAfter} in a row"
								emptyNote="Nothing has asked this feed yet."
								tone="health"
							/>
						</div>

						{#if stripDates.length > 0}
							<div
								class="feed-strip"
								data-feed-strip={feed.feedId}
								style="grid-template-columns: repeat({stripDates.length}, {stripCell.cell}px); gap: {stripCell.gap}px"
							>
								{#each stripDates as date (date)}
									{@const day = strips.get(feed.feedId)?.get(date) ?? null}
									<span
										class="feed-square"
										style="block-size: {stripCell.cell}px"
										data-feed-day={date}
										data-feed-outcome={day ? day.outcome : 'none'}
										title={day ? day.label : `${shortDate(date)}: nothing on record.`}
										aria-label="{feed.feedId} on {day
											? day.label
											: `${shortDate(date)}: nothing on record.`}"
										role="img"
									></span>
								{/each}
							</div>
						{/if}

						<p class="feed-result" data-feed-result>
							{feed.lastResult}{feed.lastDetail ? ` - ${feed.lastDetail}` : ''}
						</p>
					</li>
				{/each}
			</ol>

			{#if data.feedsHidden > 0}
				<p class="feeds-note" data-feeds-more>
					{data.feedsHidden} more {data.feedsHidden === 1 ? 'feed' : 'feeds'} had {grouped(
						data.feedsHiddenFailures
					)}
					{data.feedsHiddenFailures === 1 ? 'failure' : 'failures'} between them, none closer to a
					rest than the last row here.
				</p>
			{/if}

			{#if stripDates.length > 0}
				<div
					class="feed-axis"
					style="inline-size: {stripCell.width}px; grid-template-columns: repeat({stripDates.length}, {stripCell.cell}px); gap: {stripCell.gap}px"
				>
					{#each stripAxis as label (label.column)}
						<div class="feed-axis-slot" style="grid-column: {label.column}">
							<span style={ANCHOR[label.align]} data-day-axis data-feed-axis={label.column}
								>{label.text}</span
							>
						</div>
					{/each}
				</div>
			{:else}
				<p class="feeds-note" data-feed-strip-empty>
					The pipeline read no feed in these {windowDays} days, so there is no strip to draw.
				</p>
			{/if}

			<ul class="feed-key">
				{#each FEED_KEY as entry (entry.outcome)}
					<li><span class="feed-square" data-feed-outcome={entry.outcome}></span>{entry.text}</li>
				{/each}
			</ul>
		</div>
	{/if}

	<h2 class="console-h2">Sources close to retiring themselves</h2>

	{#if data.retiring === null}
		<p class="mt-2 text-[0.9375rem] text-text-secondary" data-retiring="absent">
			The run published no source census, so there is nothing to judge today.
		</p>
	{:else}
		{@const strip = data.retiring}
		<!-- Not windowed, and it says so. The dwell is counted against
		     `collect.source_quality_dwell_days`, which the run applied when it read
		     the record - a control that moved this span would be a control that
		     lies about what will fire. Same argument the ranking weight makes. -->
		<div
			class="console-table mt-3"
			data-retiring="table"
			data-retiring-dwell={strip.dwellDays}
			data-retiring-auto={strip.autoRetire ? 'yes' : 'no'}
			data-retiring-drawn={strip.rows.length}
			data-retiring-hidden={strip.hidden}
			data-retiring-cap={data.console.source_rows}
			data-model-rule="no"
			data-model-rule-name="source-yield"
			data-model-rule-none="a source published an address or it did not, and no model was asked"
		>
			<p class="feeds-note" data-retiring-lead>
				A source that publishes fewer than {pct(strip.alarmPoint)} of the addresses it decides,
				every day for {strip.dwellDays} days running, stops being asked.
			</p>
			<p class="feeds-note" data-retiring-clear>
				{strip.clear}
				{strip.clear === 1 ? 'judged source is' : 'judged sources are'} at or above the mark today.
			</p>
			{#if !strip.autoRetire}
				<p class="feeds-note" data-retiring-watching>
					Nothing retires on this measurement yet - this panel is watching only.
				</p>
			{/if}

			{#if strip.rows.length === 0 && strip.unjudged.length === 0}
				<p class="feeds-note" data-retiring-empty>
					No day has finished with a planned article on it, so no source has a yield to judge.
					This fills on the next run that publishes a day.
				</p>
			{:else}
				<ol class="feed-rows" data-retiring-rows>
					{#each strip.rows as row (row.sourceId)}
						<li
							class="feed-row"
							data-retiring-row={row.sourceId}
							data-retiring-days-under={row.daysUnder}
							data-retiring-on={row.retiresOn}
							data-retiring-track={row.marks.track}
						>
							<p class="feed-name">
								<span
									>{row.title}<span class="source-note-id" data-source-note-id
										>{row.sourceId}</span
									></span
								>
								{#if row.retired}
									<span class="feed-rested" data-retiring-chip>retired</span>
								{:else if row.daysLeft !== null}
									<span class="feed-rested" data-retiring-chip
										>retires in {row.daysLeft}
										{row.daysLeft === 1 ? 'day' : 'days'}</span
									>
								{/if}
							</p>

							<div class="feed-bar" data-retiring-cell="bar">
								<TargetBar
									marks={row.marks}
									label="Published out of offered"
									valueText={row.share === null ? 'no decisions' : pct(row.share)}
									targetText="retires under {pct(strip.alarmPoint)}"
									emptyNote="This source has decided nothing yet."
									tone="health"
								/>
							</div>

							{#if row.squares.length > 0}
								<div
									class="feed-strip yield-strip"
									data-retiring-strip={row.sourceId}
									style="grid-template-columns: repeat({strip.dates
										.length}, {dwellCell.cell}px); gap: {dwellCell.gap}px"
								>
									{#each row.squares as square (square.date)}
										<span
											class="feed-square"
											style="block-size: {dwellCell.cell}px"
											data-retiring-day={square.date}
											data-retiring-state={square.state}
											title={square.label}
											aria-label="{row.sourceId} on {square.label}"
											role="img"
										></span>
									{/each}
									<!-- The dwell is the AREA, not a number in a chip. It underlines
									     exactly the contiguous under-the-mark squares at the newest
									     end, so the run length is read off the picture. -->
									{#if row.daysUnder > 0}
										<span
											class="yield-dwell"
											data-retiring-dwell-rule
											style="grid-column: {strip.dates.length -
												row.daysUnder +
												1} / -1"
										></span>
									{/if}
								</div>
							{/if}

							<p class="feed-result" data-retiring-readout>
								{row.publications} published of {row.opportunities} offered, over {strip.completeDates}
								complete {strip.completeDates === 1 ? 'day' : 'days'}.{#if row.daysUnder > 0}
									Under the mark for {row.daysUnder}
									{row.daysUnder === 1 ? 'day' : 'days'} running - {row.daysUnder} of {strip.dwellDays}.{#if row.retiresOn && !row.retired}
										Retires on {row.retiresOn} if it stays there.{/if}
								{/if}
							</p>
						</li>
					{/each}
				</ol>

				{#if strip.hidden > 0}
					<p class="feeds-note" data-retiring-more>
						{strip.hidden} more {strip.hidden === 1 ? 'source is' : 'sources are'} under the mark,
						none closer to retiring than the last row here.
					</p>
				{/if}

				{#if strip.dates.length > 0}
					<div
						class="feed-axis"
						style="inline-size: {dwellCell.width}px; grid-template-columns: repeat({strip.dates
							.length}, {dwellCell.cell}px); gap: {dwellCell.gap}px"
					>
						{#each dwellAxis as label (label.column)}
							<div class="feed-axis-slot" style="grid-column: {label.column}">
								<span style={ANCHOR[label.align]} data-day-axis data-retiring-axis={label.column}
									>{label.text}</span
								>
							</div>
						{/each}
					</div>

					<ul class="feed-key">
						{#each YIELD_KEY as entry (entry.state)}
							<li>
								<span class="feed-square" data-retiring-state={entry.state}></span>{entry.text}
							</li>
						{/each}
					</ul>
				{:else}
					<!-- A view written before the day strip existed has no axis to draw on.
					     The shares above it are the run's own and still true; what is
					     missing is the day-by-day reading, so the panel says which half it
					     has rather than drawing a key for squares nobody can see. -->
					<p class="feeds-note" data-retiring-no-strip>
						The run that published this census recorded no day-by-day shares, so there is no
						strip to draw. It fills on the next run.
					</p>
				{/if}

				{#if strip.unjudged.length > 0}
					<!-- Drawn, never hidden. A source under its evidence floors has a
					     shape worth seeing; what it has not got is a number anybody may
					     act on, so the bar is a dash and the floors are printed. -->
					<p class="feeds-note" data-retiring-unjudged-lead>
						Not judged yet - under one or both evidence floors, so no countdown may be drawn.
						The record is {strip.completeDates} complete {strip.completeDates === 1
							? 'day'
							: 'days'} and a source is judged at {strip.minCompleteDays} of them plus {strip.minDecisions}
						decisions of its own. Their days are still shown, closest to being judged first.
					</p>
					<ol class="feed-rows" data-retiring-unjudged>
						{#each strip.unjudged as row (row.sourceId)}
							<li class="feed-row" data-retiring-unjudged-row={row.sourceId}>
								<p class="feed-name">
									<span
										>{row.title}<span class="source-note-id" data-source-note-id
											>{row.sourceId}</span
										></span
									>
								</p>
								<p class="yield-unjudged" data-retiring-cell="bar">not judged yet</p>
								{#if row.squares.length > 0}
									<div
										class="feed-strip yield-strip"
										data-retiring-strip={row.sourceId}
										style="grid-template-columns: repeat({strip.dates
											.length}, {dwellCell.cell}px); gap: {dwellCell.gap}px"
									>
										{#each row.squares as square (square.date)}
											<span
												class="feed-square"
												style="block-size: {dwellCell.cell}px"
												data-retiring-day={square.date}
												data-retiring-state={square.state}
												title={square.label}
												aria-label="{row.sourceId} on {square.label}"
												role="img"
											></span>
										{/each}
									</div>
								{/if}
								<p class="feed-result" data-retiring-readout>
									Decided {row.decisions} of the {row.opportunities}
									{row.opportunities === 1 ? 'address' : 'addresses'} it was offered.
								</p>
							</li>
						{/each}
					</ol>
					{#if strip.unjudgedHidden > 0}
						<p class="feeds-note" data-retiring-unjudged-more>
							{strip.unjudgedHidden} more {strip.unjudgedHidden === 1 ? 'source is' : 'sources are'}
							not judged yet either, none closer to its floors than the last row here.
						</p>
					{/if}
				{/if}
			{/if}
		</div>
	{/if}

	<div data-windowed="source-cuts" data-window-days={cuts.days}>
		<h2 class="console-h2">Sources cut short most often</h2>

		{#if cuts.cost}
			<!-- What the next move of the cap would buy, and the first line of the
			     section rather than the last. A count of cut articles says the cap
			     fired; how much it removed says whether raising it is worth
			     anything, and the n is what makes it a measurement. -->
			<p class="mt-2 text-[0.9375rem] text-text-secondary" data-source-cuts-cost>
				{cuts.cost.n} articles were cut short. Half of them lost more than {grouped(
					cuts.cost.median
				)} words each, and the longest lost {grouped(cuts.cost.max)}.
			</p>
		{/if}

		<p class="mt-1 text-[0.8125rem] text-text-tertiary" data-source-cuts-intro>
			The last {cuts.days} days, {grouped(cuts.articles)}
			{cuts.articles === 1 ? 'article' : 'articles'} between them. An article longer than the cap
			is read from the start and stopped there, so the end never reaches the machine. Sorted by how
			many articles that cost each source. A source can carry several feeds, so this list and
			"Feeds that failed" above do not name the same things. These days always end on the newest
			day the ledger holds.
		</p>

		{#if !cuts.measured}
			<p class="mt-4 text-[0.9375rem] text-text-secondary" data-source-cuts="unmeasured">
				Nothing has recorded an article length yet. This fills as runs publish.
			</p>
		{:else if cuts.rows.length === 0}
			<p class="mt-4 text-[0.9375rem] text-text-secondary" data-source-cuts="none">
				No article was cut short in these {cuts.days} days.
			</p>
		{:else}
			<div class="mt-3">
				<SourceCutRange
					rows={cuts.rows}
					caps={cuts.caps}
					width={data.console.chart_width}
				/>
			</div>

			{#if cuts.moreSources > 0}
				<p class="mt-3 text-[0.8125rem] text-text-tertiary" data-source-cuts-more>
					{cuts.moreSources} more sources had {cuts.moreCuts} cuts between them.
				</p>
			{/if}
		{/if}
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
	   share as a bar rather than printing it.

	   The tokens are `TargetBar`'s, not a second set: the track is the sunken
	   surface and the fill takes the band ramp keyed on the band `targetGeometry`
	   already decided. A discount is a health fact and the row prints the figure
	   in words beside the bar, which is the same argument `TargetBar` makes for
	   using the band ramp on the quarantine bar. */
	.track {
		position: relative;
		display: block;
		height: 0.75rem;
		border-radius: var(--radius-sm);
		background: var(--color-surface-sunken);
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
		background: var(--band-high);
		inset: 0 auto 0 0;
	}

	.track[data-band='near'] .fill {
		background: var(--band-medium);
	}

	.track[data-band='past'] .fill {
		background: var(--band-low);
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

	.feeds-note {
		margin: 0 0 var(--space-3);
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		color: var(--color-text-tertiary);
	}

	/* Two feeds in this repository are both titled "Anthropic", and the thing an
	   operator edits is one configured address. Without the id the table drew two
	   identical rows and neither said which one to go and fix. */
	.source-note-id {
		display: block;
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		color: var(--color-text-tertiary);
	}

	/* Names, not rows. There is nothing to rank and nothing to draw, so the list
	   packs into as many columns as the room allows rather than running a hundred
	   and fifty-six lines down the page. */
	.feed-clean-names {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(12rem, 1fr));
		gap: var(--space-1) var(--space-4);
		margin: var(--space-2) 0 0;
		padding: 0;
		list-style: none;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text-secondary);
	}

	/* One column set for the whole list, borrowed by every row, so a feed with a
	   two-digit count does not get a shorter bar than a feed with a one-digit one.
	   The same reason the ranked list does it. */
	.feed-rows {
		display: grid;
		grid-template-columns: minmax(8rem, 1fr) minmax(11rem, 1.4fr) auto;
		column-gap: var(--space-4);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.feed-row {
		grid-column: 1 / -1;
		display: grid;
		grid-template-columns: subgrid;
		grid-template-areas: 'name bar strip' 'result bar strip';
		align-items: center;
		padding-block: var(--space-2);
		border-block-end: 1px solid var(--color-rule);
	}

	.feed-row:last-child {
		border-block-end: 0;
	}

	.feed-name {
		grid-area: name;
		display: flex;
		align-items: center;
		gap: var(--space-2);
		margin: 0;
		font-size: var(--text-sm);
		line-height: var(--leading-sm);
		color: var(--color-text);
		overflow-wrap: anywhere;
	}

	/* The word, not the colour. A rested feed is the one thing on this list an
	   operator has to act on, so it is written out. */
	.feed-rested {
		padding-inline: var(--space-2);
		border-radius: var(--radius-full);
		background: var(--tint-bad);
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		color: var(--color-text-secondary);
		white-space: nowrap;
	}

	/* The only human-readable cause on the page, and it is never traded for a
	   glyph. It keeps its own line rather than becoming a caption on the bar. */
	.feed-result {
		grid-area: result;
		margin: 0;
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		color: var(--color-text-secondary);
	}

	.feed-bar {
		grid-area: bar;
		min-inline-size: 0;
	}

	.feed-strip,
	.feed-axis {
		display: grid;
	}

	.feed-strip {
		grid-area: strip;
	}

	.feed-square {
		display: block;
		border-radius: 2px;
		background: transparent;
	}

	/* Quarantine is a health fact and every square carries its own sentence as
	   well, so this is one of the two places a verdict ramp is the honest colour.
	   The FILL ramp, the same one the run strip uses: a square this small is a
	   solid, not type, and the band tokens are weighted to be read as type. The
	   two states that are not a verdict take no verdict colour at all. */
	.feed-square[data-feed-outcome='answered'] {
		background: var(--fill-high);
	}

	.feed-square[data-feed-outcome='failed'] {
		background: var(--fill-low);
	}

	.feed-square[data-feed-outcome='refused'] {
		background: var(--tint-neutral);
		box-shadow: inset 0 0 0 1px var(--color-rule);
	}

	.feed-square[data-feed-outcome='resting'] {
		box-shadow: inset 0 0 0 1px var(--color-rule);
	}

	/* The reliability strip reuses the feed strip's grid, and adds one row under
	   it for the dwell rule. The rule is the panel's whole argument: the dwell is
	   an AREA a reader can see, not a `9/14` chip they have to trust. */
	.yield-strip {
		grid-template-rows: auto 2px;
		row-gap: 2px;
		align-content: start;
	}

	.yield-dwell {
		grid-row: 2;
		block-size: 2px;
		border-radius: 1px;
		background: var(--fill-low);
	}

	/* The dash a source under its evidence floors gets instead of a bar. It sits
	   in the bar column rather than under the name, because the whole point of
	   drawing these rows is that the column means the same thing on every one. */
	.yield-unjudged {
		grid-area: bar;
		margin: 0;
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		color: var(--color-text-tertiary);
	}

	/* The same fill ramp the run strip and the feed strip use, for the same
	   reason: a square this small is a solid rather than type, and the band
	   tokens are weighted to be read as type. A day with no decisions is not a
	   verdict, so it takes no verdict colour. */
	.feed-square[data-retiring-state='at-or-above'] {
		background: var(--fill-high);
	}

	.feed-square[data-retiring-state='under'] {
		background: var(--fill-low);
	}

	.feed-square[data-retiring-state='nothing'] {
		background: var(--color-surface-sunken);
		box-shadow: inset 0 0 0 1px var(--color-rule);
	}

	/* Flush with the strips above it: the strip column is the last one, so it ends
	   at the same edge the list does. */
	.feed-axis {
		margin-block-start: var(--space-2);
		margin-inline-start: auto;
	}

	.feed-axis-slot {
		position: relative;
		block-size: 1rem;
	}

	.feed-axis-slot span {
		position: absolute;
		top: 0;
		white-space: nowrap;
		font-size: 0.625rem;
		line-height: 1rem;
		font-variant-numeric: tabular-nums;
		color: var(--color-text-tertiary);
	}

	.feed-key {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2) var(--space-5);
		margin: var(--space-4) 0 0;
		padding: 0;
		list-style: none;
		font-size: var(--text-xs);
		line-height: var(--leading-xs);
		color: var(--color-text-tertiary);
	}

	.feed-key li {
		display: flex;
		align-items: center;
		gap: var(--space-2);
	}

	.feed-key .feed-square {
		inline-size: 12px;
		block-size: 12px;
		flex-shrink: 0;
	}

	/* The console frame is wide, and three columns on a laptop half-window crush
	   the bar the row exists to show. Below that everything stacks. */
	@media (max-width: 48rem) {
		.feed-rows {
			grid-template-columns: minmax(0, 1fr);
		}

		.feed-row {
			grid-template-areas: 'name' 'bar' 'strip' 'result';
			row-gap: var(--space-2);
		}

		.feed-axis {
			margin-inline-start: 0;
		}
	}
</style>
