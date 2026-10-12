import { expect, test } from './support/door-page';
import { BY_ROUTE } from './support/console-expect/console';
import { readFileSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { monthsInWindow, panWindow } from '../src/lib/charts/viewport';
import { throughputWithin } from '../src/lib/server/model-work';
import { publishedCharts, telemetryMonths, telemetryRows } from '../src/lib/server/payload';
import { reliability, resultLabel, type FeedRecord } from '../src/lib/feed-health';
import { days } from './support/consecutive-days';
import { publishedSite } from './support/published-site';
/** A telemetry corpus deliberately longer than the window, for the read tests.
 *
 * The canary day carries two days, which is shorter than any window this knob
 * can hold. A window asserted against a corpus it cannot cut passes without
 * cutting anything, so the telemetry read tests read this instead.
 */
const TELEMETRY_FIXTURE = resolve(process.cwd(), 'tests', 'fixtures', 'telemetry');
test('an answer that carried nothing is labelled as such, and never as ok', () => {
    // The ledger's own word for this read is `ok` - the fetch returned 200. Printed raw it sits on
    // the same row as the failure count and contradicts it, which is how a dead feed reads as a
    // healthy one.
    const read = (outcome: string, items: number) => ({ date: '2030-06-15', runId: '2030-06-15-1', outcome, items });
    expect(resultLabel(read('ok', 0))).toBe('answered with nothing');
    expect(resultLabel(read('ok', 4))).toBe('ok');
    // A feed that really did fail still reports the reason the ledger recorded.
    expect(resultLabel(read('permanent', 0))).toBe('permanent');
});
/** The independently declared cap the feed list must keep. */
const FEED_ROWS = BY_ROUTE.voices!.feedRows!;
/** The threshold under which this page prints counts and no rate. */
const MIN_ATTEMPTS = BY_ROUTE.voices!.minAttempts!;
test('a record too shallow for a rate says so instead of printing one', () => {
    // The canary is deep enough, so the third state is driven here rather than
    // left to a sentence that never prints. Two runs deep, "did not fail" means
    // "did not fail twice", and the page has to say which it means.
    const shallow: FeedRecord[] = [
        { feedId: 'a-wire', date: '2026-08-01', runId: '2026-08-01-1', outcome: 'ok', items: 9 },
        { feedId: 'a-wire', date: '2026-08-02', runId: '2026-08-02-1', outcome: 'ok', items: 9 },
        { feedId: 'b-wire', date: '2026-08-01', runId: '2026-08-01-1', outcome: 'transient', items: 0 }
    ];
    const shallowRecord = reliability(shallow);
    expect(shallowRecord.runs).toBe(2);
    expect(shallowRecord.runs).toBeLessThan(MIN_ATTEMPTS);
    expect(shallowRecord.clean).toEqual(['a-wire']);
    expect(shallowRecord.checked).toBe(2);
    expect(shallowRecord.failed).toBe(1);
    // A feed nobody has asked is neither clean nor broken, so it is in neither
    // number. Counting a rest as a clean read is how a dead feed joins the
    // reliable list.
    const rested: FeedRecord[] = [
        ...shallow,
        { feedId: 'c-wire', date: '2026-08-01', runId: '2026-08-01-1', outcome: 'skipped', items: 0 }
    ];
    const withRest = reliability(rested);
    expect(withRest.checked).toBe(2);
    expect(withRest.clean).toEqual(['a-wire']);
    // The run count is every run the rows hold, rest or no rest.
    expect(withRest.runs).toBe(2);
    // And the partition holds, always.
    expect(withRest.clean.length + withRest.failed).toBe(withRest.checked);
});
test('a record with more failing feeds than the list draws is counted whole', () => {
    // The canary cannot show a capped list, so a record deeper than the cap is
    // written here, over five runs: twelve feeds that each failed once, in each of
    // the four ways a read fails, two that never failed, one only ever rested and
    // one only ever refused by its robots file. The page draws `feed_rows` of the
    // twelve and counts the rest in its tail sentence; the count behind both is
    // never capped.
    const runs = ['2030-06-11', '2030-06-12', '2030-06-13', '2030-06-14', '2030-06-15'];
    const record = (feedId: string, last: {
        outcome: string;
        items: number;
    }): FeedRecord[] => runs.map((date, at) => ({
        feedId,
        date,
        runId: `${date}-1`,
        ...(at === runs.length - 1 ? last : { outcome: 'ok', items: 9 })
    }));
    const failures = [
        { outcome: 'transient', items: 0 },
        { outcome: 'permanent', items: 0 },
        { outcome: 'blocked', items: 0 },
        { outcome: 'ok', items: 0 }
    ];
    const failed = Array.from({ length: 12 }, (_, at) => record(`failing-${String(at + 1).padStart(2, '0')}`, failures[at % failures.length]));
    const rows: FeedRecord[] = [
        ...failed.flat(),
        ...record('clean-a', { outcome: 'ok', items: 9 }),
        ...record('clean-b', { outcome: 'ok', items: 4 }),
        ...runs.map((date) => ({ feedId: 'rested', date, runId: `${date}-1`, outcome: 'skipped', items: 0 })),
        ...runs.map((date) => ({ feedId: 'refused', date, runId: `${date}-1`, outcome: 'robots_denied', items: 0 }))
    ];
    expect(FEED_ROWS, 'the cap reaches past this record, so it hides nothing').toBeLessThan(12);
    const measured = reliability(rows);
    expect(measured.runs).toBe(5);
    expect(measured.checked).toBe(14);
    expect(measured.failed).toBe(12);
    expect(measured.clean).toEqual(['clean-a', 'clean-b']);
    expect(measured.ineligible).toEqual(['refused', 'rested']);
});
test('a stage colour is categorical, never a health band', () => {
    const source = readFileSync(resolve(process.cwd(), 'src', 'lib', 'components', 'StageTimings.svelte'), 'utf8');
    // Green, amber and red mean good, watch and bad everywhere else on this page.
    // Lending them to the stages says the slowest one is the failing one.
    expect(source).not.toContain('--band-');
    // Three stages since 2026-08-31: `score` left this chart for the Model route,
    // and `--series-4` went with it. One series per stage and no spare.
    for (const series of ['--series-1', '--series-2', '--series-3']) {
        expect(source).toContain(series);
    }
    expect(source, 'a fourth series here means a fourth stage nobody declared').not.toContain('--series-4');
});
test("a day's two rates are its whole tokens over its whole seconds, and each run keeps its own", () => {
    // Three items over two runs, written here. Pooled, the day read 3,000 tokens in
    // 5 s and wrote 250 in 4 s. A mean of the items' own rates would say 666.67 and
    // 66.67, which weighs a short article like a long one.
    const item = (runId: string, prefillMs: number, input: number, decodeMs: number, output: number) => ({
        date: '2030-06-15',
        run_id: runId,
        prefill_ms: String(prefillMs),
        decode_ms: String(decodeMs),
        input_tokens: String(input),
        cached_tokens: '100',
        output_tokens: String(output)
    });
    const [day] = throughputWithin(new Map([
        [
            '2030-06-15',
            [
                item('2030-06-15-1', 1000, 1100, 2000, 100),
                item('2030-06-15-1', 3000, 1600, 1000, 100),
                item('2030-06-15-2', 1000, 600, 1000, 50)
            ]
        ]
    ]), new Map(), { start: '2030-06-15', end: '2030-06-15' });
    // Cached tokens are out of the read count: 3,300 asked less the 300 held.
    expect(day.readTps).toBe(600);
    expect(day.writeTps).toBe(62.5);
    expect(day.items).toBe(3);
    // The candle is the spread of the items' own rates, and each run keeps its median.
    expect(day.read).toEqual({ min: 500, p25: 500, median: 500, p75: 750, max: 1000 });
    expect(day.write).toEqual({ min: 50, p25: 50, median: 50, p75: 75, max: 100 });
    expect(day.runs).toEqual([
        { runId: '2030-06-15-1', items: 2, read: 750, write: 75 },
        { runId: '2030-06-15-2', items: 1, read: 500, write: 50 }
    ]);
});
test('a telemetry read holds exactly the window it is handed, however many months are committed', () => {
    // The fixture holds one row a day from 1 May to 10 Jul 2026, in three month
    // shards. The window ends a week before the newest row, as a console window
    // does when the projection has run on past the newest published day.
    const all = telemetryRows(TELEMETRY_FIXTURE);
    const read = telemetryRows(TELEMETRY_FIXTURE, { start: '2026-06-20', end: '2026-07-03' });
    expect(all.rows.length).toBe(71);
    expect(read.rows.map((row) => row.date)).toEqual(days('2026-06-20', 14));
    // Still the same table. The window touches June and July, the two shards a
    // read opens, however many months the pipeline has committed.
    expect(read.columns).toEqual(all.columns);
    expect(telemetryMonths(TELEMETRY_FIXTURE)).toEqual(['2026-05', '2026-06', '2026-07']);
    expect(monthsInWindow({ start: '2026-06-20', end: '2026-07-03' })).toEqual(['2026-06', '2026-07']);
});
test('the days a window read leaves out stay on disk for a pan to reach', () => {
    // Bounding the read must not put a day out of reach. The fortnight before the
    // window is in a shard the browser can still fetch by name.
    const opened = { start: '2026-06-20', end: '2026-07-03' };
    const back = panWindow(opened, -14);
    expect(back).toEqual({ start: '2026-06-06', end: '2026-06-19' });
    expect(telemetryMonths(TELEMETRY_FIXTURE)).toContain('2026-06');
    const older = telemetryRows(TELEMETRY_FIXTURE, back).rows;
    expect(older.map((row) => row.date)).toEqual(days('2026-06-06', 14));
    const readIds = new Set(telemetryRows(TELEMETRY_FIXTURE, opened).rows.map((row) => row.item_id));
    expect(older.filter((row) => readIds.has(row.item_id))).toEqual([]);
});
test('a visual that never drew is a visual and is not a published chart', () => {
    // A day that published four items: two charts that drew, one chart whose drawing
    // failed, and one with no visual. The column is headed `Visuals published` since
    // 2026-08-31 but still counts only rendered charts, because counting every visual
    // would put a picture nobody can see on chart drawing's bill and chart drawing
    // would look more productive than it is.
    const { digest } = publishedSite(test.info().outputPath('site'), { published: ['2030-06-15'] });
    const item = (n: number, visual: {
        kind: string;
        state: string;
    } | null) => ({ item_id: `item-${n}`, visual });
    writeFileSync(join(digest, '2030', '06', '15', 'digest.json'), JSON.stringify({
        date: '2030-06-15',
        items: [
            item(1, { kind: 'chart', state: 'rendered' }),
            item(2, { kind: 'chart', state: 'rendered' }),
            item(3, { kind: 'chart', state: 'render_failed' }),
            item(4, null)
        ]
    }));
    expect(publishedCharts(digest, 1)).toEqual(new Map([['2030-06-15', { items: 4, charts: 2 }]]));
});
test('the articles a day published are read off its own payload, over the days the cover reaches', () => {
    // Three published days: 4 articles on 13 Jun 2030, none on the 14th and 2 on the
    // 15th. A day that published nothing is a count of 0, never a missing day. A cover
    // of two days reaches back from the newest published day to the 14th, so the 13th
    // is never opened. The console home's cost panel takes its article counts from
    // this read, so these are the counts it divides by.
    const counts: [
        string,
        number
    ][] = [
        ['2030-06-13', 4],
        ['2030-06-14', 0],
        ['2030-06-15', 2]
    ];
    const { digest } = publishedSite(test.info().outputPath('site'), {
        published: counts.map(([date]) => date)
    });
    for (const [date, count] of counts) {
        const [year, month, day] = date.split('-');
        writeFileSync(join(digest, year, month, day, 'digest.json'), JSON.stringify({
            date,
            items: Array.from({ length: count }, (_, at) => ({ item_id: `${date}-${at + 1}`, visual: null }))
        }));
    }
    expect(publishedCharts(digest, 3)).toEqual(new Map([
        ['2030-06-15', { items: 2, charts: 0 }],
        ['2030-06-14', { items: 0, charts: 0 }],
        ['2030-06-13', { items: 4, charts: 0 }]
    ]));
    expect(publishedCharts(digest, 2)).toEqual(new Map([
        ['2030-06-15', { items: 2, charts: 0 }],
        ['2030-06-14', { items: 0, charts: 0 }]
    ]));
});
