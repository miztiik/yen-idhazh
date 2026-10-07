import { expect, test } from './support/browser';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { bandShares } from '../src/lib/charts/frame';
import { readoutCapStyle } from '../src/lib/charts/readout';
import { stacked } from '../src/lib/charts/stacked';
import {
	describeMissingMarkers,
	measurementOff,
	recordDestroyed,
	recordingNotes,
	recordingStarted,
	sampledAt,
	type OfferedWindow,
	type RecordingNotes,
	type RecordRead
} from '../src/lib/console/recording';
import { daysBetween, type HeldPeriod } from '../src/lib/data/slice';
import type { ObservabilityConfig } from '../src/lib/server/config';
import { machineCounters } from '../src/lib/server/machine-counters';
import { listManifestDays } from '../src/lib/server/model-work';
import { describeServerCounters } from '../src/lib/server/server-counter-notes';

/** `chart.readout_max_share`, read off the committed config inside the test
 * that uses it, so a malformed file fails one test rather than the module. */
function readoutMaxShare(): number {
	const config = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'config', 'appearance.json');
	return (JSON.parse(readFileSync(config, 'utf8')) as { chart: { readout_max_share: number } }).chart
		.readout_max_share;
}

/** Chart chrome, and the states a panel is in when the ledger has no answer.
 *
 * Two rules are under test and they are the whole of both rows.
 *
 * **Every chart resolves to non-empty accessible text.** Prose the page cut
 * still lives in the description, so a reader who cannot see the shape loses
 * nothing - and that is an oracle rather than a promise, because it is checked
 * on every chart of every route that draws one with a readout strip.
 *
 * **A chart that plots more than one series prints them together.** A fixed
 * strip below the plot, as wide as the plot at most, its entries side by side,
 * reachable by an arrow key. A tooltip is never the only place a value
 * appears: a tooltip needs a hover, and a hover is not a thing a thumb can do.
 */

// `/console/voices/` is NOT here, and that is a decision rather than an
// oversight. Every block below needs a strip to read, and the two day matrices
// on that route declare they have none: each square already names its own day
// and what that day did, so a strip would reprint the list the pointer is
// already on. An `if` inside this loop to walk past them is how a route list
// stops meaning one thing.
const ROUTES = ['/console/', '/console/model/', '/console/machine/', '/console/judgement/'];

test.describe('the shape switch draws one array two ways', () => {
	const COLUMNS = ['Mon', 'Tue', 'Wed'];
	const SERIES = [
		{ label: 'fetch', token: '--chart-1' as const, values: [3, 1, 4] },
		{ label: 'extract', token: '--chart-2' as const, values: [1, 5, 9] }
	];

	/** Every series' `data`, in drawing order. */
	function drawn(option: Record<string, unknown>): unknown[][] {
		const series = option.series as { data: unknown[] }[];
		return series.map((one) => one.data);
	}

	test('both shapes hand the engine byte-for-byte the same values', () => {
		const bars = stacked(COLUMNS, SERIES, 'bars');
		const lines = stacked(COLUMNS, SERIES, 'lines');

		// The row's own test for whether a chart may carry the switch at all: the
		// presence of a transform is the definition of "not cheap". If these two
		// ever disagree, the switch is re-shaping data and has to be withdrawn.
		expect(drawn(lines.option as Record<string, unknown>)).toEqual(
			drawn(bars.option as Record<string, unknown>)
		);
		expect(drawn(bars.option as Record<string, unknown>)).toEqual([
			[3, 1, 4],
			[1, 5, 9]
		]);
	});

	test('only the type and the stack differ between them', () => {
		const bars = (stacked(COLUMNS, SERIES, 'bars').option as { series: Record<string, unknown>[] })
			.series;
		const lines = (stacked(COLUMNS, SERIES, 'lines').option as { series: Record<string, unknown>[] })
			.series;

		expect(bars.map((one) => one.type)).toEqual(['bar', 'bar']);
		expect(lines.map((one) => one.type)).toEqual(['line', 'line']);
		// Stacked is the only one that stacks. A line drawn from a stack baseline
		// would be a cumulative reading wearing a line's clothes.
		expect(bars.every((one) => one.stack === 'total')).toBe(true);
		expect(lines.every((one) => one.stack === undefined)).toBe(true);
	});

	test('bars is the default, so the server and the first paint agree', () => {
		const drawnBars = (stacked(COLUMNS, SERIES).option as { series: { type: string }[] }).series;
		expect(drawnBars.map((one) => one.type)).toEqual(['bar', 'bar']);
	});
});

test.describe('a readout column sits where the engine drew it', () => {
	test('the shares account for the grid insets', () => {
		// Four columns in a 600px element with 48 left and 12 right: the plot is
		// 540 wide, a column is 135, and the first centre sits at 48 + 67.5.
		const shares = bandShares(4, 600, { left: 48, right: 12 });
		expect(shares.map((share) => Math.round(share * 600))).toEqual([116, 251, 386, 521]);
	});

	test('an element with no width and a chart with no columns give nothing', () => {
		expect(bandShares(4, 0, { left: 48, right: 12 })).toEqual([]);
		expect(bandShares(0, 600, { left: 48, right: 12 })).toEqual([]);
	});

	test('the cap is a share of the plot and never more than all of it', () => {
		expect(readoutCapStyle(0.33)).toBe('max-width: 33.00%');
		expect(readoutCapStyle(2)).toBe('max-width: 100.00%');
	});
});

test.describe('what the recording was doing, in fixed words', () => {
	/** The windows the control offers, each ending on 15 Jun 2030, the newest published day. */
	const OFFERED: OfferedWindow[] = [
		{ days: 1, start: '2030-06-15', end: '2030-06-15' },
		{ days: 7, start: '2030-06-09', end: '2030-06-15' },
		{ days: 14, start: '2030-06-02', end: '2030-06-15' },
		{ days: 30, start: '2030-05-17', end: '2030-06-15' },
		{ days: 90, start: '2030-03-18', end: '2030-06-15' }
	];

	/** A record read whole, packed as far as `through`, whose newest rows are in `lastRows`. Its
	 *  indexes begin long before every window here, which no off line reads. */
	const packed = (through: string, lastRows: HeldPeriod | null): RecordRead => ({
		state: 'read',
		through,
		first: '2029-01-01',
		lastRows,
		lostDays: [],
		setAside: {}
	});

	/** A record read whole whose indexes begin on `first`, packed as far as `through`, with
	 *  `lostDays` recorded lost. */
	const begun = (first: string, through: string, lostDays: string[] = []): RecordRead => ({
		state: 'read',
		through,
		first,
		lastRows: { period: 'daily', covers: through },
		lostDays,
		setAside: {}
	});

	/** The window from `start` to `end`, both included. */
	const over = (start: string, end: string): OfferedWindow => ({
		days: daysBetween(start, end).length,
		start,
		end
	});

	/** The line a switched-off instrument prints over the `days`-day window. */
	const offOver = (days: number, read: RecordRead, recorded: string[] = []) =>
		measurementOff({
			enabled: false,
			recorded,
			read,
			open: OFFERED.find((window) => window.days === days)!,
			offered: OFFERED
		});

	test('a measurement that is on prints no line', () => {
		expect(
			measurementOff({
				enabled: true,
				recorded: [],
				read: packed('2030-06-14', null),
				open: OFFERED[2]!,
				offered: OFFERED
			})
		).toBeNull();
	});

	test('measurement off names the newest day it recorded in the window, and never the knob', () => {
		const said = offOver(14, packed('2030-06-14', { period: 'daily', covers: '2030-06-12' }), [
			'2030-05-06',
			'2030-06-10',
			'2030-06-12'
		]);
		expect(said).toBe('Measurement is off. Nothing has been recorded since 12 Jun 2030. Turn it on in config/idhazh.json.');
		// A term from a subsystem is not a term for a user (CLAUDE.md section 0b).
		expect(said).not.toContain('host_fingerprint');
		expect(said).not.toContain('evaluation_enabled');
	});

	test('a window that holds no recorded day names none, and names the window that reaches back to the last one', () => {
		const stopped = packed('2030-06-14', { period: 'daily', covers: '2030-05-06' });
		// 6 May 2030 is the last day this record recorded, and it is in the 90-day window
		// alone, so every narrower window names that window and not the day.
		expect(offOver(7, stopped, ['2030-05-06'])).toBe(
			'Measurement is off. Nothing was recorded in these 7 days. Turn it on in config/idhazh.json. The 90-day window reaches back to the last recorded day.'
		);
		expect(offOver(30, stopped, ['2030-05-06'])).toBe(
			'Measurement is off. Nothing was recorded in these 30 days. Turn it on in config/idhazh.json. The 90-day window reaches back to the last recorded day.'
		);
		// Packed as far as the window's one day, which held no row: the window names its day.
		expect(offOver(1, packed('2030-06-15', { period: 'daily', covers: '2030-05-06' }))).toBe(
			'Measurement is off. Nothing was recorded on 15 Jun 2030. Turn it on in config/idhazh.json. The 90-day window reaches back to the last recorded day.'
		);
	});

	test('a window reaches back to a closed month only when it holds the whole month', () => {
		// The 90-day window starts on 18 Mar 2030: it holds the whole of April and part of March.
		expect(offOver(14, packed('2030-06-14', { period: 'monthly', covers: '2030-04' }))).toBe(
			'Measurement is off. Nothing was recorded in these 14 days. Turn it on in config/idhazh.json. The 90-day window reaches back to the last recorded day.'
		);
		expect(offOver(14, packed('2030-06-14', { period: 'monthly', covers: '2030-03' }))).toBe(
			'Measurement is off. Nothing was recorded in these 14 days. Turn it on in config/idhazh.json. No window here reaches back to the last recorded day.'
		);
		// The widest window can never point to a wider one.
		expect(offOver(90, packed('2030-06-14', { period: 'yearly', covers: '2029' }))).toBe(
			'Measurement is off. Nothing was recorded in these 90 days. Turn it on in config/idhazh.json. No window here reaches back to the last recorded day.'
		);
	});

	test('measurement off with nothing on record says so in every window, rather than dating it', () => {
		const never = packed('2030-06-14', null);
		for (const window of OFFERED) {
			// The 1-day window holds no packed day, and the record has still never held a row.
			expect(offOver(window.days, never), `the ${window.days}-day window`).toBe(
				'Measurement is off. Nothing has been recorded at all. Turn it on in config/idhazh.json.'
			);
		}
	});

	test('measurement off claims nothing about what was recorded where the page has not read it', () => {
		const said = 'Measurement is off. Turn it on in config/idhazh.json.';
		// Not packed yet, and a read that failed: the note above the line says which.
		expect(offOver(14, { state: 'not-packed' })).toBe(said);
		expect(offOver(14, { state: 'unreadable', at: '2030-06-10', fault: 'file-missing' })).toBe(said);
		// Packed as far as 14 Jun 2030, so the 1-day window of 15 Jun holds no packed day.
		expect(offOver(1, packed('2030-06-14', { period: 'daily', covers: '2030-05-06' }))).toBe(said);
		// The record holds rows on 12 Jun 2030 that the instrument's figures do not use.
		expect(offOver(14, packed('2030-06-14', { period: 'daily', covers: '2030-06-12' }))).toBe(said);
	});

	test('a clean fraction reads as one run in four', () => {
		expect(sampledAt(0.25)).toBe(
			'Measured on 1 run in 4. These figures count the runs we measured and are not scaled up to stand for the rest.'
		);
	});

	test('an unclean rate reads as a percentage, because 1 in 2.7 never happened', () => {
		expect(sampledAt(0.37)).toBe(
			'Measured on 37% of runs. These figures count the runs we measured and are not scaled up to stand for the rest.'
		);
	});

	test('a rate of one owes no caveat', () => {
		expect(sampledAt(1)).toBeNull();
	});

	test('the two one-sided days each name which instrument answered', () => {
		const facts = {
			enabled: true,
			recorded: ['2026-08-29'],
			window: ['2026-08-28', '2026-08-29'],
			reads: [begun('2026-08-01', '2026-08-29')],
			from: '2026-08-28',
			open: over('2026-08-28', '2026-08-29'),
			coveredElsewhere: ['2026-08-28', '2026-08-29']
		};
		expect(recordingNotes({ ...facts, missing: 'scores' }).coveredElsewhere).toBe(
			'There are no quality figures for 28 Aug 2026. The machine ran and we timed it, but nothing scored the summaries.'
		);
		expect(recordingNotes({ ...facts, missing: 'server-counters' }).coveredElsewhere).toBe(
			'No server figures were written down for 28 Aug 2026. The speed figures for that day come from the summariser, not the server.'
		);
	});

	test('a start inside the window counts the days before it that had a run, in Reader\'s words', () => {
		expect(recordingStarted('2026-08-27', 5)).toBe(
			'Server figures started on 27 Aug 2026. Earlier in this window, 5 days had a run but no server figures.'
		);
		// Each instrument names what started and what it lacks: the summary checker's figures are
		// quality figures, and the machine record is one record, so its line opens on "The".
		expect(recordingStarted('2026-08-27', 5, 'quality figures')).toBe(
			'Quality figures started on 27 Aug 2026. Earlier in this window, 5 days had a run but no quality figures.'
		);
		expect(recordingStarted('2026-08-27', 5, 'machine record')).toBe(
			'The machine record started on 27 Aug 2026. Earlier in this window, 5 days had a run but no machine record.'
		);
	});

	test('one day reads as one day, and no gap reads as nothing at all', () => {
		expect(recordingStarted('2026-08-27', 1)).toBe(
			'Server figures started on 27 Aug 2026. Earlier in this window, 1 day had a run but no server figures.'
		);
		expect(recordingStarted('2026-08-27', 0)).toBeNull();
		expect(recordingStarted(null, 4)).toBeNull();
	});

	test('a live instrument that started mid-window says only that', () => {
		const notes = recordingNotes({
			enabled: true,
			rate: 1,
			recorded: ['2026-08-27', '2026-08-28'],
			window: ['2026-08-25', '2026-08-26', '2026-08-27', '2026-08-28'],
			reads: [begun('2026-08-27', '2026-08-28')],
			from: '2026-08-25',
			open: over('2026-08-25', '2026-08-28')
		});
		expect(notes.sampled).toBeNull();
		expect(notes.startedMidWindow).toBe(
			'Server figures started on 27 Aug 2026. Earlier in this window, 2 days had a run but no server figures.'
		);
	});

	test('a record that began before the days it is handed is never said to start in the window, though the window starts with days it missed', () => {
		// The counters' first day in the window is 27 Aug 2026. Only the window's days are
		// handed, and their record's indexes begin on 1 Aug, before them: what the record did
		// before 25 Aug is not in hand, so recording may not have started on the 27th.
		const facts = {
			enabled: true,
			recorded: ['2026-08-27', '2026-08-28'],
			window: ['2026-08-25', '2026-08-26', '2026-08-27', '2026-08-28'],
			from: '2026-08-25',
			open: over('2026-08-25', '2026-08-28')
		};
		expect(recordingNotes({ ...facts, reads: [begun('2026-08-01', '2026-08-28')] }).startedMidWindow).toBeNull();
		// Begun on the first day handed: the record's whole history is in hand.
		expect(recordingNotes({ ...facts, reads: [begun('2026-08-25', '2026-08-28')] }).startedMidWindow).toBe(
			'Server figures started on 27 Aug 2026. Earlier in this window, 2 days had a run but no server figures.'
		);
	});

	test('an instrument that began after its record did names its own first day in every window that shows it', () => {
		// The record's indexes begin on 1 Aug 2026, the route read from 25 Jul, and this
		// instrument's rows begin on 10 Aug: in hand is everything the record did, so the 10th
		// is when this instrument started.
		const facts = {
			enabled: true,
			recorded: daysBetween('2026-08-10', '2026-08-20'),
			window: daysBetween('2026-07-25', '2026-08-20'),
			reads: [begun('2026-08-01', '2026-08-20')],
			from: '2026-07-25'
		};
		expect(recordingNotes({ ...facts, open: over('2026-08-05', '2026-08-20') }).startedMidWindow).toBe(
			'Server figures started on 10 Aug 2026. Earlier in this window, 5 days had a run but no server figures.'
		);
		// A window that does not show the 10th says nothing of it.
		expect(recordingNotes({ ...facts, open: over('2026-08-12', '2026-08-20') }).startedMidWindow).toBeNull();
		// Handed only the window's days, the start is not known, so it is not said.
		expect(
			recordingNotes({ ...facts, from: '2026-08-05', open: over('2026-08-05', '2026-08-20') }).startedMidWindow
		).toBeNull();
	});

	test('an instrument drawn from two records dates its start only where both reach back to their first days', () => {
		// The shared rule, for an instrument whose rows come from two records. Here one record
		// began on 1 Sep 2026, inside the read from 25 Aug, and the instrument's first day in the
		// read is 30 Aug.
		const facts = {
			enabled: true,
			recorded: daysBetween('2026-08-30', '2026-09-10'),
			window: daysBetween('2026-08-25', '2026-09-10'),
			from: '2026-08-25',
			open: over('2026-08-25', '2026-09-10')
		};
		const later = begun('2026-09-01', '2026-09-10');
		expect(recordingNotes({ ...facts, reads: [later, begun('2026-08-25', '2026-09-10')] }).startedMidWindow).toBe(
			'Server figures started on 30 Aug 2026. Earlier in this window, 5 days had a run but no server figures.'
		);
		// The other record began on 1 Aug, before the read, so it may hold a day the instrument ran
		// before anything the read holds.
		expect(recordingNotes({ ...facts, reads: [later, begun('2026-08-01', '2026-09-10')] }).startedMidWindow).toBeNull();
		// A day either record lost is a day the instrument ran.
		expect(
			recordingNotes({ ...facts, reads: [later, begun('2026-08-25', '2026-09-10', ['2026-08-28'])] }).startedMidWindow
		).toBe('Server figures started on 28 Aug 2026. Earlier in this window, 3 days had a run but no server figures.');
	});

	test('a window\'s lines name only what it shows, though the route hands it every day it read', () => {
		// The route read 29 days, 31 Jul to 28 Aug 2026, and hands every window all of them. The
		// record began on 3 Aug, before the 7-day window of 22 to 28 Aug, so only the wider window
		// may say when recording started.
		const lines = (open: OfferedWindow) =>
			recordingNotes({
				enabled: true,
				recorded: daysBetween('2026-08-03', '2026-08-28'),
				window: daysBetween('2026-07-31', '2026-08-28'),
				reads: [begun('2026-08-03', '2026-08-28')],
				from: '2026-07-31',
				open
			});
		expect(lines(over('2026-08-22', '2026-08-28')).startedMidWindow).toBeNull();
		expect(lines(over('2026-07-31', '2026-08-28')).startedMidWindow).toBe(
			'Server figures started on 3 Aug 2026. Earlier in this window, 3 days had a run but no server figures.'
		);
	});

	test('a switched-off instrument owes no sampling caveat as well', () => {
		const notes = recordingNotes({
			enabled: false,
			rate: 0.25,
			recorded: ['2030-06-12'],
			window: ['2030-06-12'],
			reads: [begun('2030-06-12', '2030-06-14')],
			from: OFFERED[2]!.start,
			open: OFFERED[2]!
		});
		expect(offOver(14, packed('2030-06-14', { period: 'daily', covers: '2030-06-12' }), ['2030-06-12'])).toBe(
			'Measurement is off. Nothing has been recorded since 12 Jun 2030. Turn it on in config/idhazh.json.'
		);
		// Two sentences about the same absence is one too many: a measurement that
		// is off was not sampled, it was not taken.
		expect(notes.sampled).toBeNull();
	});

	test('a day another instrument covered is named, not drawn as a quiet day', () => {
		const facts = {
			enabled: true,
			rate: 1,
			recorded: ['2026-08-29'],
			window: ['2026-08-28', '2026-08-29'],
			reads: [begun('2026-08-01', '2026-08-29')],
			from: '2026-08-28',
			coveredElsewhere: ['2026-08-28', '2026-08-29'],
			missing: 'server-counters' as const
		};
		expect(recordingNotes({ ...facts, open: over('2026-08-28', '2026-08-29') }).coveredElsewhere).toBe(
			'No server figures were written down for 28 Aug 2026. The speed figures for that day come from the summariser, not the server.'
		);
		// A day another instrument covered outside the window is not this window's to name.
		expect(recordingNotes({ ...facts, open: over('2026-08-29', '2026-08-29') }).coveredElsewhere).toBeNull();
	});

	test('a day that published and kept no row is a loss, not a quiet day', () => {
		// The fixture is the state that destroyed 303 rows on 2026-09-16: the day
		// file exists and holds only its header, and the digest for that date
		// carries articles. Built, never read off the archive - a case the archive
		// holds today ages out of every window, and a test timed to go red on a
		// date nobody set is a fuse (`CLAUDE.md` section 13).
		const notes = recordingNotes({
			enabled: true,
			recorded: ['2026-09-17'],
			window: ['2026-09-16', '2026-09-17'],
			reads: [begun('2026-09-16', '2026-09-17')],
			from: '2026-09-16',
			open: over('2026-09-16', '2026-09-17'),
			lost: [{ date: '2026-09-16', articles: 431 }],
			figures: 'machine record'
		});
		// The whole point. Counted as a gap, the lost day would date the record's
		// own start to the day AFTER the loss and hand that back as the reason.
		expect(notes.startedMidWindow).toBeNull();
		expect(notes.recordDestroyed).toBe(
			'This day published 431 articles and its machine record is missing. The run worked; what it measured about the machine did not survive.'
		);
	});

	test('a gap and a loss are told apart inside one window', () => {
		// A window wide enough to reach days before the record shipped AND to hold
		// the day it lost. Both sentences are owed, and neither may absorb the
		// other: one says go and look at the instrument, one says open an incident.
		const notes = recordingNotes({
			enabled: true,
			recorded: ['2026-09-17'],
			window: ['2026-09-14', '2026-09-15', '2026-09-16', '2026-09-17'],
			reads: [begun('2026-09-16', '2026-09-17')],
			from: '2026-09-14',
			open: over('2026-09-14', '2026-09-17'),
			lost: [{ date: '2026-09-16', articles: 431 }],
			figures: 'machine record'
		});
		// The record ran on the day it lost, so that day dates its start; the day
		// after the loss would be the lie the loss sentence exists to stop.
		expect(notes.startedMidWindow).toBe(
			'The machine record started on 16 Sep 2026. Earlier in this window, 2 days had a run but no machine record.'
		);
		expect(notes.recordDestroyed).not.toBeNull();
	});

	test('a day the record has no record for is a day it ran, never a day before it started', () => {
		// The record's own index says the day was lost: an empty day, then a lost one,
		// then the first day with rows. Counted the old way, the note said recording
		// started on the day after the loss.
		const notes = recordingNotes({
			enabled: true,
			recorded: ['2026-08-20'],
			window: ['2026-08-17', '2026-08-19', '2026-08-20'],
			reads: [begun('2026-08-17', '2026-08-20', ['2026-08-19'])],
			from: '2026-08-17',
			open: over('2026-08-17', '2026-08-20'),
			figures: 'machine record'
		});
		expect(notes.startedMidWindow).toBe(
			'The machine record started on 19 Aug 2026. Earlier in this window, 1 day had a run but no machine record.'
		);
		const lostFirst = recordingNotes({
			enabled: true,
			recorded: ['2026-08-20'],
			window: ['2026-08-19', '2026-08-20'],
			reads: [begun('2026-08-19', '2026-08-20', ['2026-08-19'])],
			from: '2026-08-19',
			open: over('2026-08-19', '2026-08-20')
		});
		expect(lostFirst.startedMidWindow).toBeNull();
	});

	test('a day the record kept a row of is never counted as lost', () => {
		// The caller does the join over two ledgers, so the one thing this can be
		// handed is a date the record answered for after all.
		const notes = recordingNotes({
			enabled: true,
			recorded: ['2026-09-16', '2026-09-17'],
			window: ['2026-09-16', '2026-09-17'],
			reads: [begun('2026-09-16', '2026-09-17')],
			from: '2026-09-16',
			open: over('2026-09-16', '2026-09-17'),
			lost: [{ date: '2026-09-16', articles: 431 }]
		});
		expect(notes.recordDestroyed).toBeNull();
	});

	test('several lost days are one sentence that counts them', () => {
		expect(recordDestroyed([])).toBeNull();
		expect(
			recordDestroyed([
				{ date: '2026-09-15', articles: 400 },
				{ date: '2026-09-16', articles: 31 }
			])
		).toBe(
			'2 days published 431 articles between them and their machine record is missing. The runs worked; what they measured about the machine did not survive.'
		);
		// One article reads as one article, because "1 articles" is the tell that a
		// sentence was assembled rather than written.
		expect(recordDestroyed([{ date: '2026-09-16', articles: 1 }])).toContain('published 1 article and');
	});

	test('an instrument with no sampling knob owes no sampling caveat', () => {
		const notes = recordingNotes({
			enabled: true,
			recorded: ['2026-09-17'],
			window: ['2026-09-17'],
			reads: [begun('2026-09-17', '2026-09-17')],
			from: '2026-09-17',
			open: over('2026-09-17', '2026-09-17')
		});
		expect(notes.sampled).toBeNull();
	});

	test.describe("THE ORACLE: a one-sided line names only the days the article record alone answered for, in Reader's words", () => {
		/** The 14-day window from 23 Sep to 6 Oct 2026. The article record timed a run on every day of it. */
		const FORTNIGHT = daysBetween('2026-09-23', '2026-10-06');
		const WINDOW = over('2026-09-23', '2026-10-06');
		/** Every day of the window but `days`. */
		const except = (...days: string[]): string[] => FORTNIGHT.filter((day) => !days.includes(day));
		/** Every line the notes print, whichever field holds it, so a line is checked absent by what
		 *  the page would say rather than by where it sits. */
		const printed = (notes: RecordingNotes): string[] =>
			Object.values(notes).filter((line): line is string => line !== null);
		/** Both records read whole, packed as far as 6 Oct 2026. They began on 1 Aug, before the
		 *  days handed here, so no started line prints. */
		const BOTH = [begun('2026-08-01', '2026-10-06'), begun('2026-08-01', '2026-10-06')];

		/** Summaries: the scorer, handed only the window's days, with the days it scored. */
		const scorer = (recorded: readonly string[], read: RecordRead, open: OfferedWindow = WINDOW, enabled = true) =>
			recordingNotes({
				enabled,
				recorded,
				window: FORTNIGHT,
				reads: [read],
				from: WINDOW.start,
				open,
				figures: 'quality figures',
				coveredElsewhere: FORTNIGHT,
				missing: 'scores'
			});

		/** Hardware: the server's counters, drawn from the machine and the article records, with the
		 *  days they hold a run of. */
		const counters = (recorded: readonly string[], open: OfferedWindow = WINDOW, reads: RecordRead[] = BOTH) =>
			recordingNotes({
				enabled: true,
				recorded,
				window: FORTNIGHT,
				reads,
				from: WINDOW.start,
				open,
				coveredElsewhere: FORTNIGHT,
				missing: 'server-counters'
			});

		test('a day the score record lost is a day the scorer ran, so no line says nothing scored it', () => {
			// Scored on every day but 3 Oct 2026, which the score record recorded lost. The record
			// note names that day; this line has nothing to add.
			expect(printed(scorer(except('2026-10-03'), begun('2026-08-01', '2026-10-06', ['2026-10-03'])))).toEqual([]);
		});

		test('two days nothing scored are named in one line, and never called this day', () => {
			const lines = printed(scorer(except('2026-10-01', '2026-10-03'), begun('2026-08-01', '2026-10-06')));
			expect(lines).toEqual([
				'There are no quality figures for 1 Oct and 3 Oct 2026. The machine ran and we timed it, but nothing scored the summaries.'
			]);
			expect(lines.join(' ')).not.toContain('this day');
		});

		test('on Hardware a day with articles and no counters says where its speed figures came from, and claims no score', () => {
			// The article record holds 2 Oct 2026, the machine record holds no counters row for it,
			// and Hardware reads no score row for its line at all.
			const lines = printed(counters(except('2026-10-02')));
			expect(lines).toEqual([
				'No server figures were written down for 2 Oct 2026. The speed figures for that day come from the summariser, not the server.'
			]);
			expect(lines.join(' ')).not.toContain('scored');
		});

		test('a day the missing record has not packed yet, or a record that did not read, gets no line', () => {
			// The score record is packed as far as 4 Oct 2026, so nothing is known yet of 5 and 6 Oct.
			expect(printed(scorer(except('2026-10-05', '2026-10-06'), begun('2026-08-01', '2026-10-04')))).toEqual([]);
			// The counters draw on two records, and the one packed less far decides.
			const behind = [begun('2026-08-01', '2026-10-04'), begun('2026-08-01', '2026-10-06')];
			expect(printed(counters(except('2026-10-05', '2026-10-06'), WINDOW, behind))).toEqual([]);
			expect(printed(scorer([], { state: 'not-packed' }))).toEqual([]);
			expect(printed(scorer([], { state: 'unreadable', at: '2026-10-01', fault: 'file-missing' }))).toEqual([]);
		});

		test('a day the started line counts is said there, once', () => {
			// The score record began on 25 Sep 2026, inside the read, and the scorer first scored on
			// 26 Sep. 23 to 25 Sep had a run before it started; 2 Oct had a run it did not score.
			const lines = printed(
				recordingNotes({
					enabled: true,
					recorded: daysBetween('2026-09-26', '2026-10-06').filter((day) => day !== '2026-10-02'),
					window: FORTNIGHT,
					reads: [begun('2026-09-25', '2026-10-06')],
					from: WINDOW.start,
					open: WINDOW,
					figures: 'quality figures',
					coveredElsewhere: FORTNIGHT,
					missing: 'scores'
				})
			);
			expect(lines).toEqual([
				'Quality figures started on 26 Sep 2026. Earlier in this window, 3 days had a run but no quality figures.',
				'There are no quality figures for 2 Oct 2026. The machine ran and we timed it, but nothing scored the summaries.'
			]);
		});

		test('while measurement is off, the off line speaks for the days after the newest one recorded', () => {
			// Switched off after 30 Sep 2026, and the record packed on through 6 Oct with no rows.
			// Before the switch the scorer missed 27 Sep, a gap only this line names.
			const stopped = (covers: string): RecordRead => ({
				state: 'read',
				through: '2026-10-06',
				first: '2026-08-01',
				lastRows: { period: 'daily', covers },
				lostDays: [],
				setAside: {}
			});
			const recorded = daysBetween('2026-09-23', '2026-09-30').filter((day) => day !== '2026-09-27');
			expect(measurementOff({ enabled: false, recorded, read: stopped('2026-09-30'), open: WINDOW, offered: [WINDOW] })).toBe(
				'Measurement is off. Nothing has been recorded since 30 Sep 2026. Turn it on in config/idhazh.json.'
			);
			expect(printed(scorer(recorded, stopped('2026-09-30'), WINDOW, false))).toEqual([
				'There are no quality figures for 27 Sep 2026. The machine ran and we timed it, but nothing scored the summaries.'
			]);
			// Nothing recorded in the window: the off line speaks for every day of it.
			expect(printed(scorer([], stopped('2026-09-10'), WINDOW, false))).toEqual([]);
		});

		test("every day on screen takes the window's own words, and one day never needs a second", () => {
			const lastDay = over('2026-10-06', '2026-10-06');
			expect(printed(scorer(except('2026-10-06'), begun('2026-08-01', '2026-10-06'), lastDay))).toEqual([
				'There are no quality figures for this one day. The machine ran and we timed it, but nothing scored the summaries.'
			]);
			expect(printed(counters(except('2026-10-06'), lastDay))).toEqual([
				'No server figures were written down for this one day. The speed figures here come from the summariser, not the server.'
			]);
			// No counters on any of the 7 days from 30 Sep 2026.
			expect(printed(counters(daysBetween('2026-09-23', '2026-09-29'), over('2026-09-30', '2026-10-06')))).toEqual([
				'No server figures were written down for these 7 days. The speed figures here come from the summariser, not the server.'
			]);
			expect(printed(counters(except('2026-10-01', '2026-10-03')))).toEqual([
				'No server figures were written down for 1 Oct and 3 Oct 2026. The speed figures for those days come from the summariser, not the server.'
			]);
			// Consecutive days are one run of dates.
			expect(
				printed(scorer(except('2026-09-24', '2026-09-25', '2026-09-26'), begun('2026-08-01', '2026-10-06')))
			).toEqual([
				'There are no quality figures for 24 Sep to 26 Sep 2026. The machine ran and we timed it, but nothing scored the summaries.'
			]);
		});
	});

	test.describe("THE ORACLE: Hardware's lines say only what its records hold", () => {
		/** The observability block as the route holds it: everything on, every run scored. */
		const OBSERVABILITY: ObservabilityConfig = {
			cost_currency: 'USD',
			cost_input_per_million: 0.2,
			cost_output_per_million: 0.6,
			evaluation_enabled: true,
			host_fingerprint: true,
			host_fingerprint_bandwidth_cache_multiple: 2,
			sample_rate: 1
		};
		/** Shard 0 of run `run` on `date`, as the machine record files it from the work job: the probe
		 *  and the clocks, and the two cells the server itself wrote where `server` is true. */
		const machineRow = (date: string, server: boolean, run = 1): Record<string, string> => ({
			date,
			run_id: `${date}-${run}`,
			job: 'work',
			shard: '0',
			fingerprint: 'f00d',
			cpu_model: 'Test CPU',
			job_seconds: '600',
			model_load_ms: '2000',
			server_prompt_tokens: server ? '900' : '',
			server_prompt_seconds: server ? '9' : ''
		});
		/** An article that shard 0 of run `run` on `date` summarised, as the article record files it. */
		const articleRow = (date: string, run = 1): Record<string, string> => ({
			date,
			run_id: `${date}-${run}`,
			machine_job: 'work',
			machine_shard: '0'
		});
		/** The runs `machineCounters` forms from the two records' rows. */
		const runsOf = (machine: Record<string, string>[], articles: Record<string, string>[]) =>
			machineCounters(machine, articles, new Map(), { contextWindow: null, jobTimeoutSeconds: null }).runs;
		/** Every line the notes print, whichever field holds it. */
		const printed = (notes: RecordingNotes): string[] =>
			Object.values(notes).filter((line): line is string => line !== null);
		/** The window of `days` days the control offers. */
		const offered = (days: number): OfferedWindow => OFFERED.find((window) => window.days === days)!;

		/** The article record holds rows from 20 May 2030, and article rows formed a run every day from
		 *  25 May to 14 Jun. The machine record began on 1 Jun: on 5 Jun its row held the probe and the
		 *  clocks and no server cell, from 6 Jun its rows carried the server's two cells, and on 12 Jun
		 *  it filed no row, so that day's run is article rows alone. */
		const ARTICLE_DAYS = daysBetween('2030-05-20', '2030-06-14');
		const HISTORY = runsOf(
			[
				machineRow('2030-06-05', false),
				...daysBetween('2030-06-06', '2030-06-14')
					.filter((day) => day !== '2030-06-12')
					.map((day) => machineRow(day, true))
			],
			daysBetween('2030-05-25', '2030-06-14').map((day) => articleRow(day))
		);
		/** What Hardware says about the server's counters over `open`, handed what the route hands. */
		const hardware = (
			open: OfferedWindow,
			runs = HISTORY,
			observability = OBSERVABILITY,
			machineRead: RecordRead = begun('2030-06-01', '2030-06-14')
		) =>
			describeServerCounters({
				runs,
				ran: ARTICLE_DAYS,
				articleDays: ARTICLE_DAYS,
				machineRead,
				from: offered(90).start,
				open,
				offered: OFFERED,
				observability
			});

		test("the intro counts every run in the window, and how many of them carry the server's own figures", () => {
			expect(OFFERED.map((open) => [open.days, hardware(open).intro])).toEqual([
				[1, 'This one day has no run on record. 2030-06-15.'],
				[7, '6 runs in these 7 days, 5 of them with figures from the model server itself. 2030-06-09 to 2030-06-15.'],
				[14, '13 runs in these 14 days, 8 of them with figures from the model server itself. 2030-06-02 to 2030-06-15.'],
				[30, '21 runs in these 30 days, 8 of them with figures from the model server itself. 2030-05-17 to 2030-06-15.'],
				[90, '21 runs in these 90 days, 8 of them with figures from the model server itself. 2030-03-18 to 2030-06-15.']
			]);
		});

		test("the intro's share reads right at every count, in Reader's words", () => {
			/** The intro over the `days`-day window for runs on 15 Jun 2030, one a flag: true where the
			 *  run carried the server's figures. */
			const intro = (servers: boolean[], days: number) =>
				hardware(
					offered(days),
					runsOf(
						servers.map((server, index) => machineRow('2030-06-15', server, index + 1)),
						servers.map((_, index) => articleRow('2030-06-15', index + 1))
					)
				).intro;
			const week = '2030-06-09 to 2030-06-15.';
			expect(intro([true, true], 7)).toBe(`2 runs in these 7 days, each with figures from the model server itself. ${week}`);
			expect(intro([true, false, false], 7)).toBe(`3 runs in these 7 days, 1 of them with figures from the model server itself. ${week}`);
			expect(intro([false, false], 7)).toBe(`2 runs in these 7 days, none with figures from the model server itself. ${week}`);
			expect(intro([true], 7)).toBe(`1 run in these 7 days, with figures from the model server itself. ${week}`);
			expect(intro([false], 7)).toBe(`1 run in these 7 days, with no figures from the model server itself. ${week}`);
			expect(intro([], 7)).toBe(`No run in these 7 days is on record. ${week}`);
			expect(intro([true, true], 1)).toBe('This one day had 2 runs, each with figures from the model server itself. 2030-06-15.');
			expect(intro([true, false, false], 1)).toBe('This one day had 3 runs, 1 of them with figures from the model server itself. 2030-06-15.');
			expect(intro([false, false], 1)).toBe('This one day had 2 runs, none with figures from the model server itself. 2030-06-15.');
			expect(intro([true], 1)).toBe('This one day had 1 run, with figures from the model server itself. 2030-06-15.');
			expect(intro([false], 1)).toBe('This one day had 1 run, with no figures from the model server itself. 2030-06-15.');
			expect(intro([], 1)).toBe('This one day has no run on record. 2030-06-15.');
		});

		test("the server's figures are dated from the first run that carried them, never from article rows alone", () => {
			expect(OFFERED.map((open) => [open.days, hardware(open).recording.startedMidWindow])).toEqual([
				[1, null],
				[7, null],
				[14, 'Server figures started on 6 Jun 2030. Earlier in this window, 4 days had a run but no server figures.'],
				[30, 'Server figures started on 6 Jun 2030. Earlier in this window, 17 days had a run but no server figures.'],
				[90, 'Server figures started on 6 Jun 2030. Earlier in this window, 17 days had a run but no server figures.']
			]);
		});

		test('a day of article rows alone, after the server figures started, is named as a day without them', () => {
			const line =
				'No server figures were written down for 12 Jun 2030. The speed figures for that day come from the summariser, not the server.';
			expect(printed(hardware(offered(7)).recording)).toEqual([line]);
			expect(printed(hardware(offered(14)).recording)).toEqual([
				'Server figures started on 6 Jun 2030. Earlier in this window, 4 days had a run but no server figures.',
				line
			]);
		});

		test("with measurement off, nothing is said to be recorded after the newest run that carried the server's figures", () => {
			// Switched off after 11 Jun 2030: the machine record filed nothing more, and article rows
			// kept forming runs to 14 Jun.
			const runs = runsOf(
				daysBetween('2030-06-06', '2030-06-11').map((day) => machineRow(day, true)),
				daysBetween('2030-06-06', '2030-06-14').map((day) => articleRow(day))
			);
			const stopped: RecordRead = {
				state: 'read',
				through: '2030-06-14',
				first: '2030-06-01',
				lastRows: { period: 'daily', covers: '2030-06-11' },
				lostDays: [],
				setAside: {}
			};
			const notes = hardware(offered(7), runs, { ...OBSERVABILITY, host_fingerprint: false }, stopped);
			expect(notes.measurementOff).toBe(
				'Measurement is off. Nothing has been recorded since 11 Jun 2030. Turn it on in config/idhazh.json.'
			);
			// The off line speaks for the days after it, so no other line names them.
			expect(printed(notes.recording)).toEqual([]);
		});

		test("the scorer's sampling rate is never the server's: at 0.25 Hardware prints no sampled line", () => {
			expect(printed(hardware(offered(7), HISTORY, { ...OBSERVABILITY, sample_rate: 0.25 }).recording)).toEqual([
				'No server figures were written down for 12 Jun 2030. The speed figures for that day come from the summariser, not the server.'
			]);
		});

		test('while the sampled line prints, Summaries names no day as one only the article record answered for', () => {
			// The scorer missed 12 Jun 2030; the article record timed a run on every day of the window.
			const summaries = (rate: number) =>
				recordingNotes({
					enabled: true,
					rate,
					recorded: daysBetween('2030-06-09', '2030-06-15').filter((day) => day !== '2030-06-12'),
					window: daysBetween('2030-06-09', '2030-06-15'),
					reads: [begun('2030-01-01', '2030-06-15')],
					from: offered(7).start,
					open: offered(7),
					figures: 'quality figures',
					coveredElsewhere: daysBetween('2030-06-09', '2030-06-15'),
					missing: 'scores'
				});
			expect(printed(summaries(0.25))).toEqual([
				'Measured on 1 run in 4. These figures count the runs we measured and are not scaled up to stand for the rest.'
			]);
			// Every run scored: the day nothing scored is named.
			expect(printed(summaries(1))).toEqual([
				'There are no quality figures for 12 Jun 2030. The machine ran and we timed it, but nothing scored the summaries.'
			]);
		});

		test.describe('a score read that did not read is named on the charts it cost a marker, never silent', () => {
			/** Runs on 2 to 14 Jun 2030, and run manifests name what ran from 6 Jun. */
			const RAN = daysBetween('2030-06-02', '2030-06-14');
			const IDENTIFIED = listManifestDays(
				daysBetween('2030-06-06', '2030-06-14').map((date) => ({ date, records: [{ inputs: { model: 'test-model' } }] }))
			);
			const lost = (read: RecordRead, open = offered(14), ran = RAN, identified = IDENTIFIED) =>
				describeMissingMarkers({ read, ran, identified, open });
			const others = ' This chart shows every change on the other days.';

			test('each state names its own cause, and the days whose marker only the score record could give', () => {
				const on = 'This chart cannot show whether the setup changed on 2 Jun to 5 Jun 2030, because';
				expect(lost({ state: 'not-packed' })).toBe(
					`${on} the score record has not been packed yet. That is a step not yet run.${others}`
				);
				expect(lost({ state: 'unreadable', at: null, fault: null })).toBe(
					`${on} the score record's list of packed days did not load. This is a fault to fix.${others}`
				);
				expect(lost({ state: 'unreadable', at: '2030-05-30', fault: null })).toBe(
					`${on} the score record's day for 30 May 2030 did not load. This is a fault to fix.${others}`
				);
				expect(lost({ state: 'unreadable', at: '2030-06-03', fault: 'file-missing' })).toBe(
					`${on} the score record lists a packed file for 3 Jun 2030 that is not there. This is a fault to fix.${others}`
				);
				expect(lost({ state: 'unreadable', at: '2030-06-03', fault: 'day-missing' })).toBe(
					`${on} the score record is missing 3 Jun 2030, a day between packed days. This is a fault to fix.${others}`
				);
			});

			test('one day, and every day on screen, read as such', () => {
				// The manifests name every day with a run but 4 Jun.
				expect(lost({ state: 'not-packed' }, offered(14), RAN, RAN.filter((day) => day !== '2030-06-04'))).toBe(
					`This chart cannot show whether the setup changed on 4 Jun 2030, because the score record has not been packed yet. That is a step not yet run.${others}`
				);
				// A run on every day of the window and no manifest: there are no other days.
				expect(lost({ state: 'not-packed' }, offered(7), daysBetween('2030-06-09', '2030-06-15'), [])).toBe(
					'This chart cannot show whether the setup changed on these 7 days, because the score record has not been packed yet. That is a step not yet run.'
				);
				expect(lost({ state: 'not-packed' }, offered(1), ['2030-06-15'], [])).toBe(
					'This chart cannot show whether the setup changed on this one day, because the score record has not been packed yet. That is a step not yet run.'
				);
			});

			test('no line where no marker was lost', () => {
				expect(lost(begun('2030-01-01', '2030-06-14'))).toBeNull();
				// Every day of the window with a run is one a manifest names.
				expect(lost({ state: 'not-packed' }, offered(7))).toBeNull();
				// A day before the window is not this window's to name.
				expect(lost({ state: 'not-packed' }, offered(7), daysBetween('2030-06-02', '2030-06-05'), [])).toBeNull();
			});
		});
	});
});

for (const route of ROUTES) {
	test(`every chart on ${route} resolves to non-empty accessible text`, async ({ page }) => {
		await page.goto(route, { waitUntil: 'domcontentloaded' });

		// Prose cut from the visible page lives here, so this is the oracle that
		// says a screen-reader reader lost nothing. It may not regress.
		const named = await page.locator('svg[role="img"], figure.chart').evaluateAll((nodes) =>
			nodes.map((node) => {
				const own = (node.getAttribute('aria-label') ?? '').trim();
				const by = node.getAttribute('aria-describedby');
				const referenced = by
					? (by
							.split(/\s+/)
							.map((id) => document.getElementById(id)?.textContent ?? '')
							.join(' ')
							.trim() ?? '')
					: '';
				return { text: own || referenced, tag: node.tagName.toLowerCase() };
			})
		);

		expect(named.length, 'the route drew at least one chart').toBeGreaterThan(0);
		expect(named.filter((one) => one.text.length === 0)).toEqual([]);
	});

	test(`every readout strip on ${route} stays inside its cap and lays its entries side by side`, async ({
		page
	}) => {
		await page.goto(route, { waitUntil: 'domcontentloaded' });

		const strips = page.locator('[data-readout]');
		const count = await strips.count();
		expect(count, 'the route prints at least one readout').toBeGreaterThan(0);
		const cap = readoutMaxShare();

		for (let at = 0; at < count; at += 1) {
			const strip = strips.nth(at);
			// Either spelling of the same share. The server writes `100.00%` and
			// Svelte's client-side setter normalises it to `100%`, so since
			// 2026-09-09 - when the console started drawing charts from rows it
			// fetches, and their strips are created in the browser - one page
			// carries both. The number is what this checks.
			const style = await strip.getAttribute('style');
			expect(style, 'the strip carries its own cap').toMatch(/max-width: \d+(\.\d+)?%/);
			const share = Number((style ?? '').replace(/[^\d.]/g, ''));
			expect(share).toBeLessThanOrEqual(cap * 100 + 0.005);

			// Below the plot, never over it. A strip that floats can cover the mark
			// it is explaining, and a floating box that dodges moves it instead.
			await expect(strip).toHaveCSS('position', 'static');

			// The defect this layout replaced: a cap of a third of the plot left a
			// phone's strip 119 px wide and stacked every entry on a line of its
			// own. An entry may start a new line only where it would not have
			// fitted on the line before it. A new line is read from where the entry
			// starts, not from its top: the strip aligns entries on their baseline,
			// so two on one line can sit a few pixels apart vertically. There is no
			// slack in the fit: the browser wraps an entry that misses by a fifth of
			// a pixel, and a box is measured exactly, to a sixty-fourth of one.
			const early = await strip.evaluate((node) => {
				const room = node.getBoundingClientRect().right;
				const gap = parseFloat(getComputedStyle(node).columnGap) || 0;
				const boxes = [...node.querySelectorAll(':scope > [data-readout-row]')].map((entry) =>
					entry.getBoundingClientRect()
				);
				return boxes.filter(
					(box, index) =>
						index > 0 &&
						box.left <= boxes[index - 1].left + 1 &&
						boxes[index - 1].right + gap + box.width <= room + 0.02
				).length;
			});
			expect(early, 'an entry went to a new line while it fitted on the last one').toBe(0);
		}
	});

	test(`every readout strip on ${route} opens on a column rather than blank`, async ({ page }) => {
		await page.goto(route, { waitUntil: 'domcontentloaded' });

		const heads = page.locator('[data-readout] [data-readout-day]');
		const count = await heads.count();
		expect(count).toBeGreaterThan(0);
		for (let at = 0; at < count; at += 1) {
			await expect(heads.nth(at)).not.toHaveText('');
		}
	});
}

test('a hand-written multi-series chart prints every series at one column', async ({ page }) => {
	await page.goto('/console/', { waitUntil: 'domcontentloaded' });

	// The failure chart is the hardest shape on the page to read one band off:
	// columns on the left axis, a rate line per stage on the right. Comparing them
	// by eye is what the strip replaces, and four hovers is what it replaces.
	const strip = page.locator('[data-readout="failure-rate"]');
	await expect(strip).toHaveCount(1);

	const rows = await strip
		.locator('[data-readout-row]')
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-readout-row') ?? ''));
	expect(rows.length, 'more than one series is printed').toBeGreaterThan(1);
	expect(new Set(rows).size, 'no series is printed twice').toBe(rows.length);
	// Where the items stopped AND what share that was, at one column. A stack
	// without its own rate beside it is the reading this chart exists to refuse.
	expect(rows.some((row) => row.endsWith(' rate'))).toBe(true);
});

test('an engine-drawn chart prints both its series at one column', async ({ page }) => {
	await page.goto('/console/machine/', { waitUntil: 'domcontentloaded' });

	// The two-clocks chart is the one this rule exists for: two readings of one
	// quantity on a shared axis, which is exactly the comparison a reader would
	// otherwise make by eye, one hover at a time.
	const strip = page.locator('[data-readout="clocks"]');
	await expect(strip, 'the two-instrument chart carries a strip').toHaveCount(1);

	const rows = await strip
		.locator('[data-readout-row]')
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-readout-row') ?? ''));
	// Both instruments, and the gap between them, at the column the reader is on.
	expect(rows).toEqual(['Item ledger', 'Model server', 'Apart']);
});

test('an arrow key moves an engine chart readout and draws a guide', async ({ page }) => {
	await page.goto('/console/machine/', { waitUntil: 'domcontentloaded' });

	// One column a run, and a run id is unique, so the column Home lands on can
	// never print what the resting column prints.
	const frame = page.locator('[data-chart-readout="read-against-written"]');
	await expect(frame).toHaveCount(1);
	const head = page.locator('[data-readout="read-against-written"] [data-readout-day]');
	const resting = await head.textContent();

	// The keyboard is the point. A tooltip that only a pointer can raise leaves
	// a value with nowhere to appear on a phone or under a screen reader.
	await frame.focus();
	await page.keyboard.press('Home');
	await expect(page.locator('[data-chart-guide="read-against-written"]')).toHaveCount(1);
	expect(await head.textContent()).not.toBe(resting);

	// Escape returns it to rest, and the guide goes with it.
	await page.keyboard.press('Escape');
	await expect(page.locator('[data-chart-guide="read-against-written"]')).toHaveCount(0);
	expect(await head.textContent()).toBe(resting);
});

test('the shape switch is one control per panel and reaches the chart', async ({ page }) => {
	await page.goto('/console/machine/', { waitUntil: 'domcontentloaded' });

	// The counterfactual panel carries the one switch on this route that names
	// shapes; the other two name units and grains.
	const control = page.locator('[data-shape-switch="cost-shape"]');
	await expect(control, 'one control, not one per series').toHaveCount(1);
	await expect(control).toHaveAttribute('data-shape', 'daily');
	const chart = page.locator('[data-chart-readout="counterfactual-cost"]');

	// The label, not the input: the segment box sits over it, which is exactly the
	// trap `console-window.spec.ts` already records for the window presets.
	await control.locator('[data-shape-option="running"]').click();
	await expect(control).toHaveAttribute('data-shape', 'running');
	// And it reaches the chart rather than only its own fieldset. The accessible
	// name is where a reader who cannot see the marks is told which shape it is,
	// so a switch that moved the radio and left the drawing named as before is a
	// defect this file owns.
	await expect(chart, 'the chart is still named as the shape the switch left').toHaveAttribute(
		'aria-label',
		/added up day by day/
	);
	await control.locator('[data-shape-option="daily"]').click();
	await expect(control).toHaveAttribute('data-shape', 'daily');
	await expect(chart).toHaveAttribute('aria-label', /one column a day/);
});

test('a route in a state says which state, in fixed words', async ({ page }) => {
	await page.goto('/console/machine/', { waitUntil: 'domcontentloaded' });

	// The states are the panel rather than a replacement for it, so the heading
	// above them is still there. A route that hid itself until it had data would
	// be a route nobody knew to check.
	await expect(page.locator('[data-machine="intro"]')).toHaveCount(1);

	const notes = await page
		.locator('[data-recording]')
		.evaluateAll((nodes) =>
			nodes.map((node) => ({
				state: node.getAttribute('data-recording') ?? '',
				text: (node.textContent ?? '').trim()
			}))
		);
	expect(notes.length, 'the fixture reaches at least one recording state').toBeGreaterThan(0);
	for (const note of notes) {
		expect(note.text.length).toBeGreaterThan(0);
		// Never the knob's name, and never styled as an error.
		expect(note.text).not.toContain('host_fingerprint');
		expect(note.text).not.toContain('evaluation_enabled');
		expect(note.text).not.toContain('sample_rate');
	}
});

test('Summaries prints its recording lines before its first section, never inside it', async ({ page }) => {
	await page.goto('/console/model/', { waitUntil: 'domcontentloaded' });

	// One group, printed whatever the sections below hold. Inside the section, which
	// prints only when the widest window holds model data, the "Measurement is off"
	// line went unsaid on the page that needed it most.
	await expect(page.locator('[data-recording-lines]')).toHaveCount(1);
	await expect(page.locator('[data-model-section] [data-recording]')).toHaveCount(0);
	await expect(page.locator('[data-model-section] [data-recording-lines]')).toHaveCount(0);
	const beforeHeading = await page.evaluate(() => {
		const group = document.querySelector('[data-recording-lines]');
		const heading = [...document.querySelectorAll('h2')].find(
			(node) => (node.textContent ?? '').trim() === 'What the model did'
		);
		if (group === null || heading === undefined) return false;
		return (group.compareDocumentPosition(heading) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
	});
	expect(beforeHeading, 'the recording lines are not above the first section').toBe(true);
});

// The route-wide sweep for a nought standing in for an absent reading lived
// here, and its only instrument was the host panel's own `data-host-value`
// cells. With that panel gone the sweep had nothing to walk. What is left is
// the per-panel rule, which is where the fault would be written: the memory
// board's absent cells in `console-memory-board.spec.ts` and the shard cells in
// `console-machine-data.spec.ts`. What nobody checks now is a NEW panel landing
// on this route with the fault, which is a check the panel that lands owes.
