/** Deterministic failures rules over bounded fixtures; no browser, build, or layout matrix. */
import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { causeKey, datesIn, failedRows, failureLedger, failureRowKey, sourceLosses, type TelemetryRow } from '../src/lib/charts/series';
import { rank, tailSentence, type Rankable, type RankedDisplay } from '../src/lib/charts/rank';
import type { TimeWindow } from '../src/lib/charts/viewport';
import { telemetryRow } from './support/telemetry-row';
const frontend = process.cwd();
const SOURCE_ROWS = (JSON.parse(readFileSync(resolve(frontend, '..', 'config', 'appearance.json'), 'utf8')) as {
    console?: {
        source_rows?: number;
    };
}).console?.source_rows ?? 10;
function builtRows(): TelemetryRow[] {
    const COUNTS = [529, 97, 61, 40, 25, 16, 10, 6, 4, 2, 1];
    const STAGES = ['fetch', 'extract', 'summarize'];
    const rows: TelemetryRow[] = [];
    const row = (over: {
        date?: string;
        run_id?: string;
        item_id: string;
        source_id?: string;
        stage?: string;
        outcome?: string;
        code?: string;
    }): TelemetryRow => telemetryRow({
        date: over.date ?? '2026-08-20',
        run_id: over.run_id ?? '1',
        item_id: over.item_id,
        vertical: 'world',
        source_id: over.source_id ?? 'src-00',
        stage: over.stage ?? 'fetch',
        outcome: over.outcome ?? 'failed',
        code: over.code ?? 'unreachable'
    });
    let made = 0;
    COUNTS.forEach((count, cause) => {
        for (let index = 0; index < count; index += 1) {
            made += 1;
            rows.push(row({
                date: `2026-08-${String(20 + (made % 5)).padStart(2, '0')}`,
                item_id: `world-${String(made).padStart(10, '0')}`,
                source_id: `src-${String(made % 14).padStart(2, '0')}`,
                stage: STAGES[cause % STAGES.length],
                code: `code-${String(cause).padStart(2, '0')}`
            }));
        }
    });
    rows.push(row({ item_id: 'world-0000000001', run_id: '2', date: '2026-08-21' }));
    rows.push(row({ item_id: 'world-9999999999', outcome: 'ok', code: '' }));
    return rows;
}
function wholeSpan(rows: TelemetryRow[]): TimeWindow {
    const dates = datesIn(rows);
    return { start: dates[0], end: dates[dates.length - 1] };
}
test.describe('the failure ledger', () => {
    const rows = builtRows();
    test('the counts sum to the failed rows in the window', () => {
        const window = wholeSpan(rows);
        const ledger = failureLedger(rows, window);
        const failed = failedRows(rows, window, null);
        const summed = ledger.causes.reduce((total, cause) => total + cause.count, 0);
        expect(summed, 'the ledger and the list disagree about how many items failed').toBe(failed.length);
        expect(ledger.failed).toBe(failed.length);
    });
    test('selecting each cause in turn partitions the list, with no overlap and no remainder', () => {
        const window = wholeSpan(rows);
        const ledger = failureLedger(rows, window);
        const failed = failedRows(rows, window, null);
        const covered = new Set<TelemetryRow>();
        for (const cause of ledger.causes) {
            const slice = failedRows(rows, window, null, cause.key);
            expect(slice.length, `the ledger's count for ${cause.key} is not its rows`).toBe(cause.count);
            for (const row of slice) {
                expect(covered.has(row), `a row falls under two causes at ${cause.key}`).toBe(false);
                covered.add(row);
                expect(causeKey(row)).toBe(cause.key);
            }
        }
        expect(covered.size, 'the causes cover fewer rows than the list holds').toBe(failed.length);
        const missed = failed.filter((row) => !covered.has(row));
        expect(missed, 'these failed rows belong to no cause').toEqual([]);
    });
    test('a cause spans no more days than the window, and its trend adds up to its count', () => {
        const window = wholeSpan(rows);
        const ledger = failureLedger(rows, window);
        for (const cause of ledger.causes) {
            const daily = cause.daily.reduce((total, n) => total + n, 0);
            expect(daily, `${cause.key} draws a trend that is not its own count`).toBe(cause.count);
            expect(cause.lastAgo).toBeGreaterThanOrEqual(0);
            expect(cause.last >= window.start && cause.last <= window.end).toBe(true);
        }
    });
    test('breadth is read against the sources the window saw, not against the failures', () => {
        const window = wholeSpan(rows);
        const ledger = failureLedger(rows, window);
        const sources = new Set(rows
            .filter((row) => row.date >= window.start && row.date <= window.end)
            .map((row) => row.source_id)
            .filter(Boolean));
        expect(ledger.sourcesSeen).toBe(sources.size);
        for (const cause of ledger.causes) {
            expect(cause.sources).toBeGreaterThan(0);
            expect(cause.sources).toBeLessThanOrEqual(ledger.sourcesSeen);
        }
    });
    test('the ledger is uncapped, and the cap is the list that draws it', () => {
        const window = wholeSpan(rows);
        const ledger = failureLedger(rows, window);
        const entries: Rankable<RankedDisplay>[] = ledger.causes.map((cause) => ({
            key: cause.key,
            value: cause.count,
            row: { label: cause.code, value: `${cause.count}` }
        }));
        const capped = rank(entries, 3);
        expect(capped.rows.length).toBe(3);
        expect(capped.hidden).toBe(ledger.causes.length - 3);
        expect(capped.hidden + capped.rows.length).toBe(ledger.causes.length);
        expect(capped.rows.map((row) => row.value)).toEqual([...capped.rows.map((row) => row.value)].sort((a, b) => b - a));
    });
    test('every drawn row has a key of its own, under every cause and under none', () => {
        const window = wholeSpan(rows);
        const ledger = failureLedger(rows, window);
        const lists = [
            failedRows(rows, window, null),
            ...ledger.causes.map((cause) => failedRows(rows, window, null, cause.key))
        ];
        for (const list of lists) {
            const keys = new Set(list.map((row, index) => failureRowKey(row, index)));
            expect(keys.size).toBe(list.length);
        }
        const colliding = failedRows(rows, window, null).slice(0, 1);
        expect(colliding.length, 'the projection holds no failed row to build on').toBe(1);
        const twice = [colliding[0], { ...colliding[0] }];
        expect(new Set(twice.map((row) => `${row.run_id}-${row.item_id}`)).size).toBe(1);
        expect(new Set(twice.map((row, index) => failureRowKey(row, index))).size).toBe(2);
    });
    test('a window with no row at all is not a window with no failure', () => {
        const empty = failureLedger(rows, { start: '1999-01-01', end: '1999-01-31' });
        expect(empty.rows).toBe(0);
        expect(empty.causes).toEqual([]);
        expect(empty.failed).toBe(0);
    });
});
interface HandLoss {
    key: string;
    lost: number;
    articles: number;
}
function lossesByHand(rows: TelemetryRow[], window: TimeWindow): HandLoss[] {
    const lost = new Map<string, Set<string>>();
    const seen = new Map<string, Set<string>>();
    for (const row of rows) {
        if (row.date < window.start || row.date > window.end)
            continue;
        if (!row.source_id)
            continue;
        const article = `${row.date}\u0000${row.item_id}`;
        seen.set(row.source_id, (seen.get(row.source_id) ?? new Set<string>()).add(article));
        if (row.outcome !== 'failed')
            continue;
        lost.set(row.source_id, (lost.get(row.source_id) ?? new Set<string>()).add(article));
    }
    return [...lost].map(([key, articles]) => ({
        key,
        lost: articles.size,
        articles: (seen.get(key) as Set<string>).size
    }));
}
function sourceEntries(rows: TelemetryRow[], window: TimeWindow): Rankable<RankedDisplay>[] {
    return sourceLosses(rows, window).sources.map((source) => ({
        key: source.key,
        value: source.lost,
        tiebreak: -source.lastAgo,
        row: { label: source.key, value: `${source.lost} of ${source.articles} articles` }
    }));
}
test.describe('THE ORACLE: sources ranked by the articles their failures cost', () => {
    const rows = builtRows();
    test('the rows carry more sources than the cap draws', () => {
        const window = wholeSpan(rows);
        const byHand = lossesByHand(rows, window);
        expect(byHand.length, 'no source carries a loss').toBeGreaterThan(SOURCE_ROWS);
        expect(byHand.reduce((total, source) => total + source.lost, 0), 'no article was lost, so a ranking of losses says nothing').toBeGreaterThan(0);
    });
    test('the ledger names the same sources and the same losses as a hand count', () => {
        const window = wholeSpan(rows);
        const measured = sourceLosses(rows, window);
        const byHand = new Map(lossesByHand(rows, window).map((source) => [source.key, source]));
        expect(new Set(measured.sources.map((source) => source.key))).toEqual(new Set(byHand.keys()));
        for (const source of measured.sources) {
            const hand = byHand.get(source.key) as HandLoss;
            expect(source.lost, `${source.key} lost a different number of articles`).toBe(hand.lost);
            expect(source.articles, `${source.key} saw a different number of articles`).toBe(hand.articles);
            expect(source.lost).toBeLessThanOrEqual(source.articles);
            expect(source.causes).toBeGreaterThan(0);
            expect(source.cause === null, `${source.key} names a cause it does not have`).toBe(source.causes !== 1);
            if (source.cause !== null) {
                const seen = new Set(failedRows(rows, window, null, null, source.key).map((row) => causeKey(row)));
                expect(seen).toEqual(new Set([source.cause]));
            }
        }
        expect(measured.lost).toBe([...byHand.values()].reduce((total, source) => total + source.lost, 0));
    });
    test('an article a second run failed again on the same day is one article', () => {
        const window = { start: '2026-08-01', end: '2026-08-01' };
        const row: TelemetryRow = telemetryRow({
            date: '2026-08-01',
            run_id: '2026-08-01-1',
            item_id: 'ai-1234567890',
            source_id: 'a-wire',
            stage: 'fetch',
            outcome: 'failed',
            code: 'http_client_error'
        });
        const twice = [row, { ...row, run_id: '2026-08-01-2' }];
        expect(failedRows(twice, window, null)).toHaveLength(2);
        expect(sourceLosses(twice, window).sources[0].lost).toBe(1);
        expect(sourceLosses(twice, window).lost).toBe(1);
    });
    test('the drawn rows are the top of the ranking, in that order', () => {
        const window = wholeSpan(rows);
        const drawn = rank(sourceEntries(rows, window), SOURCE_ROWS);
        const byHand = [...lossesByHand(rows, window)].sort((a, b) => b.lost - a.lost || a.key.localeCompare(b.key));
        expect(drawn.rows).toHaveLength(SOURCE_ROWS);
        for (const [index, row] of drawn.rows.entries()) {
            expect(row.value, `row ${index} is not the ${index + 1}th largest loss`).toBe(byHand[index].lost);
        }
        expect(drawn.rows.map((row) => row.value)).toEqual([...drawn.rows.map((row) => row.value)].sort((a, b) => b - a));
        expect(drawn.max).toBe(byHand[0].lost);
    });
    test('the tail sentence counts and sums exactly what the cap left out', () => {
        const window = wholeSpan(rows);
        const drawn = rank(sourceEntries(rows, window), SOURCE_ROWS);
        const byHand = [...lossesByHand(rows, window)].sort((a, b) => b.lost - a.lost || a.key.localeCompare(b.key));
        const rest = byHand.slice(SOURCE_ROWS);
        expect(drawn.hidden).toBe(rest.length);
        expect(drawn.hiddenValue).toBe(rest.reduce((total, source) => total + source.lost, 0));
        expect(drawn.rows.length + drawn.hidden).toBe(byHand.length);
        const sentence = tailSentence(drawn, {
            one: 'source',
            many: 'sources',
            unitOne: 'lost article',
            unitMany: 'lost articles'
        });
        expect(sentence).toBe(`${drawn.hidden} more sources had ${drawn.hiddenValue} lost articles between them.`);
    });
    test('selecting a source narrows the rows to exactly the matching set', () => {
        const window = wholeSpan(rows);
        const measured = sourceLosses(rows, window);
        const failed = failedRows(rows, window, null);
        const covered = new Set<TelemetryRow>();
        for (const source of measured.sources) {
            const slice = failedRows(rows, window, null, null, source.key);
            expect(slice.length, `${source.key} draws no row for a loss it claims`).toBeGreaterThan(0);
            expect(new Set(slice.map((row) => `${row.date}\u0000${row.item_id}`)).size).toBe(source.lost);
            for (const row of slice) {
                expect(row.source_id, `a foreign source is in ${source.key}'s rows`).toBe(source.key);
                expect(covered.has(row), `a row falls under two sources at ${source.key}`).toBe(false);
                covered.add(row);
            }
        }
        const named = failed.filter((row) => row.source_id);
        expect(covered.size, 'the sources cover fewer rows than the list holds').toBe(named.length);
    });
    test('a code chip and a source narrow together, not instead of each other', () => {
        const window = wholeSpan(rows);
        const measured = sourceLosses(rows, window);
        const source = measured.sources[0].key;
        const code = failedRows(rows, window, null, null, source)[0].code;
        const both = failedRows(rows, window, code, null, source);
        expect(both.length).toBeGreaterThan(0);
        for (const row of both) {
            expect(row.source_id).toBe(source);
            expect(row.code).toBe(code);
        }
        expect(both.length).toBeLessThanOrEqual(failedRows(rows, window, null, null, source).length);
    });
    test('a window with no row at all is not a window with no loss', () => {
        const empty = sourceLosses(rows, { start: '1999-01-01', end: '1999-01-31' });
        expect(empty.rows).toBe(0);
        expect(empty.sources).toEqual([]);
        expect(empty.lost).toBe(0);
    });
});
