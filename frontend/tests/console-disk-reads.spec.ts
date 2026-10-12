/** Deterministic disk reads rules over bounded fixtures; no browser, build, or layout matrix. */
import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { diskReads, type DiskReadMarks } from '../src/lib/console/machine/disk-reads';
function consoleConfig(): {
    model_disk_reads_marked: number;
    model_disk_reads_named: number;
    window_presets: number[];
    default_window_days: number;
} {
    return (JSON.parse(readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')) as {
        console: {
            model_disk_reads_marked: number;
            model_disk_reads_named: number;
            window_presets: number[];
            default_window_days: number;
        };
    }).console;
}
function marks(): DiskReadMarks {
    const config = consoleConfig();
    return { marked: config.model_disk_reads_marked, named: config.model_disk_reads_named };
}
function itemRow(cells: Record<string, string | number>): Record<string, string> {
    const row: Record<string, string> = {};
    for (const [key, value] of Object.entries(cells))
        row[key] = String(value);
    return row;
}
test.describe('the fold, as arithmetic', () => {
    test('a day counts the articles that were not first on their shard, and only those', () => {
        const reading = diskReads([
            itemRow({ date: '2026-09-02', run_id: 'r1', item_index: 0, llama_major_faults: 100 }),
            itemRow({ date: '2026-09-02', run_id: 'r1', item_index: 1, llama_major_faults: 11 }),
            itemRow({ date: '2026-09-02', run_id: 'r1', item_index: 2, llama_major_faults: 22 }),
            itemRow({ date: '2026-09-02', run_id: 'r2', llama_major_faults: 300 })
        ], marks());
        const day = reading.days[0];
        expect(day.reads, 'the day summed a first or unseated article').toBe(33);
        expect(day.counted, 'the day counted the wrong articles').toBe(2);
        expect(day.excluded, 'the day did not report the articles it left out').toBe(2);
    });
    test('a row that never said where in its shard it sat is excluded, not counted as second', () => {
        const reading = diskReads([
            itemRow({ date: '2026-09-02', run_id: 'r1', llama_major_faults: 4000 }),
            itemRow({ date: '2026-09-02', run_id: 'r1', item_index: 1, llama_major_faults: 11 })
        ], marks());
        expect(reading.days[0].reads).toBe(11);
        expect(reading.days[0].excluded).toBe(1);
    });
    test('a day nothing counted is unrecorded, and unrecorded is not a zero', () => {
        const reading = diskReads([itemRow({ date: '2026-09-02', run_id: 'r1', item_index: 1 })], marks());
        expect(reading.days[0].reads).toBeNull();
        expect(reading.days[0].state).toBe('unrecorded');
        expect(reading.recorded).toBe(0);
    });
    test('a day that counted and found nothing is quiet, which is the opposite fact', () => {
        const reading = diskReads([itemRow({ date: '2026-09-02', run_id: 'r1', item_index: 1, llama_major_faults: 0 })], marks());
        expect(reading.days[0].reads).toBe(0);
        expect(reading.days[0].state).toBe('quiet');
        expect(reading.recorded).toBe(1);
    });
    test('a day only fires once it reaches the mark the config sets', () => {
        const { marked } = marks();
        const at = (waits: number) => diskReads([itemRow({ date: '2026-09-02', run_id: 'r1', item_index: 1, llama_major_faults: waits })], { marked, named: marked }).days[0].state;
        expect(at(marked - 1)).toBe('quiet');
        expect(at(marked)).toBe('fired');
    });
    test('the disk copies fall as a share of that day\'s own high, not of the machine', () => {
        const reading = diskReads([
            itemRow({ date: '2026-09-02', run_id: 'r1', item_index: 1, os_mem_cached_bytes: 8000000000 }),
            itemRow({ date: '2026-09-02', run_id: 'r1', item_index: 2, os_mem_cached_bytes: 2000000000 })
        ], marks());
        expect(reading.days[0].copiesHigh).toBe(8000000000);
        expect(reading.days[0].copiesLow).toBe(2000000000);
        expect(reading.days[0].copiesFell).toBeCloseTo(0.75, 6);
    });
    test('a day that recorded no copies at all reports null, which draws no mark', () => {
        const reading = diskReads([itemRow({ date: '2026-09-02', run_id: 'r1', item_index: 1, llama_major_faults: 9 })], marks());
        expect(reading.days[0].copiesFell).toBeNull();
    });
    test('the setting is counted once a run, and a run that said nothing is silent', () => {
        const reading = diskReads([
            itemRow({ date: '2026-09-02', run_id: 'held', machine_shard: 0, weights_pinned: 'True' }),
            itemRow({ date: '2026-09-02', run_id: 'held', machine_shard: 1, weights_pinned: 'True' }),
            itemRow({ date: '2026-09-02', run_id: 'loose', machine_shard: 0, weights_pinned: 'False' }),
            itemRow({ date: '2026-09-02', run_id: 'quiet-run', machine_shard: 0 })
        ], marks());
        expect(reading.pinning).toEqual({ held: 1, loose: 1, silent: 1 });
    });
    test('a run whose shards disagree is loose - one of them could be taken from', () => {
        const reading = diskReads([
            itemRow({ date: '2026-09-02', run_id: 'split', machine_shard: 0, weights_pinned: 'True' }),
            itemRow({ date: '2026-09-02', run_id: 'split', machine_shard: 1, weights_pinned: 'False' })
        ], marks());
        expect(reading.pinning).toEqual({ held: 0, loose: 1, silent: 0 });
    });
    test('the worst day is the loudest one that reached the naming mark, not the newest', () => {
        const reading = diskReads([
            itemRow({ date: '2026-09-01', run_id: 'r1', item_index: 1, llama_major_faults: 900 }),
            itemRow({ date: '2026-09-02', run_id: 'r2', item_index: 1, llama_major_faults: 5 })
        ], { marked: 1, named: 100 });
        expect(reading.worst?.date).toBe('2026-09-01');
        expect(reading.reads).toBe(905);
        expect(reading.fired).toBe(2);
    });
    test('no day reaching the naming mark leaves the panel with no day to name', () => {
        const reading = diskReads([itemRow({ date: '2026-09-02', run_id: 'r1', item_index: 1, llama_major_faults: 5 })], { marked: 1, named: 100 });
        expect(reading.worst).toBeNull();
        expect(reading.days[0].state).toBe('fired');
    });
});
