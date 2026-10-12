import { expect, test } from '@playwright/test';
import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { daySlots } from '../src/lib/charts/day-slots';
import { slotCellFor } from '../src/lib/charts/run-history';
import { health, runOutcome, squareLabel, type RunFacts } from '../src/lib/console/run-square';
import { loadManifests } from '../src/lib/server/payload';
import { publishedSite } from './support/published-site';
test('a run manifest reads into the facts its square and its line are built from', () => {
    // Two published days. 14 Jun 2030 has no manifest, and reads as no row rather
    // than a day of zeros. 15 Jun 2030 ran twice: run 1 completed, tried 8 articles
    // of the 9 it planned, published 6, failed 2 and skipped 1, on two shards, with
    // the planner timed; run 2 reused yesterday's list of sources and failed on all
    // 3 it planned. The day's site size is the last run's, never a sum.
    const { digest } = publishedSite(test.info().outputPath('site'), {
        published: ['2030-06-14', '2030-06-15']
    });
    const model = { model_ref: { id: 'model-a' } };
    writeFileSync(join(digest, '2030', '06', '15', 'run.json'), JSON.stringify({
        date: '2030-06-15',
        runs: [
            {
                run_id: '2030-06-15-1',
                n: 1,
                status: 'completed',
                started_at: '2030-06-15T06:00:00Z',
                items_planned: 9,
                items_succeeded: 6,
                items_failed: 2,
                items_skipped: 1,
                source_list_stale: false,
                shards: 2,
                items_routed: 5,
                items_prefiltered: 3,
                charts_drafted: 2,
                chart_evidence: {
                    displayed_values: 7,
                    derived_values: 1,
                    trusted_values: 7,
                    derived_value_rate: 1 / 7,
                    trusted_data_ratio: 1
                },
                route_ms: 90000,
                inputs: { summarizer: 'model-a' },
                models: [model],
                site_bytes: 2400000,
                site_files: 39
            },
            {
                run_id: '2030-06-15-2',
                n: 2,
                status: 'failed',
                started_at: '2030-06-15T12:00:00Z',
                items_planned: 3,
                items_succeeded: 0,
                items_failed: 3,
                items_skipped: 0,
                source_list_stale: true,
                route_ms: null,
                models: [model],
                site_bytes: 2500000,
                site_files: 40
            }
        ]
    }));
    const days = loadManifests(digest, 2);
    expect(days.map((day) => day.date)).toEqual(['2030-06-15']);
    const [day] = days;
    expect(day).toMatchObject({
        runs: 2,
        planned: 12,
        failed: 5,
        siteBytes: 2500000,
        siteFiles: 40,
        models: ['model-a']
    });
    expect(day.records).toEqual([
        {
            runId: '2030-06-15-1',
            n: 1,
            status: 'completed',
            planned: 9,
            succeeded: 6,
            failed: 2,
            skipped: 1,
            startedAt: '2030-06-15T06:00:00Z',
            sourceListStale: false,
            shards: 2,
            decided: 5,
            prefiltered: 3,
            chartsDrafted: 2,
            chartEvidence: {
                displayed_values: 7,
                derived_values: 1,
                trusted_values: 7,
                derived_value_rate: 1 / 7,
                trusted_data_ratio: 1
            },
            decisionMs: 90000,
            inputs: { summarizer: 'model-a' }
        },
        {
            runId: '2030-06-15-2',
            n: 2,
            status: 'failed',
            planned: 3,
            succeeded: 0,
            failed: 3,
            skipped: 0,
            startedAt: '2030-06-15T12:00:00Z',
            sourceListStale: true,
            shards: null,
            decided: 0,
            prefiltered: 0,
            chartsDrafted: 0,
            chartEvidence: null,
            // Nothing timed the planner, and the manifest says so with a null: a zero
            // here would be a measurement nobody took.
            decisionMs: null,
            inputs: null
        }
    ]);
    // What each square says, and the line beside it, at a floor of 70 percent.
    expect(day.records.map((run) => squareLabel(day.date, run, 70, 0))).toEqual([
        'Run 1 on 15 Jun 2030: 6 of 8 succeeded, 2 failed, 1 skipped',
        "Run 2 on 15 Jun 2030: 0 of 3 succeeded, under 70%, 3 failed, reused yesterday's list of sources, the run failed"
    ]);
});
test('a square carries the whole run in one sentence', () => {
    // The square's accessible name and the readout line are built from one set
    // of facts, and the line carries every clause the name does - the strip is
    // where a keyboard and a thumb read a run, so it may not be the shorter of
    // the two. They are checked together here, and against the colour the same
    // facts give.
    const floor = 70;
    const run = (facts: Partial<RunFacts>): RunFacts => ({
        n: 1,
        status: 'completed',
        succeeded: 0,
        failed: 0,
        skipped: 0,
        sourceListStale: false,
        ...facts
    });
    const clean = run({ succeeded: 8 });
    expect(squareLabel('2026-08-20', clean, floor, 0)).toBe('Run 1 on 20 Aug 2026: 8 of 8 succeeded');
    expect(runOutcome(clean, floor, 0)).toBe('8 of 8 succeeded');
    expect(health(clean, floor)).toBe('green');
    // Nothing tried: a run that skipped everything it planned.
    const idle = run({ n: 2, skipped: 4 });
    expect(squareLabel('2026-08-20', idle, floor, 0)).toBe('Run 2 on 20 Aug 2026: nothing new to try, 4 skipped');
    expect(runOutcome(idle, floor, 0)).toBe('nothing new to try, 4 skipped');
    expect(health(idle, floor)).toBe('amber');
    // A crash that took every article with it, in the order the clauses are read.
    const broke = run({ n: 3, failed: 5, status: 'failed' });
    expect(squareLabel('2026-08-20', broke, floor, 0)).toBe('Run 3 on 20 Aug 2026: 0 of 5 succeeded, under 70%, 5 failed, the run failed');
    expect(runOutcome(broke, floor, 0)).toBe('0 of 5 succeeded, under 70%, 5 failed, the run failed');
    expect(health(broke, floor)).toBe('red');
    // Under the floor without crashing, and cut short, and on yesterday's sources.
    const thin = run({ n: 4, succeeded: 6, failed: 4, sourceListStale: true });
    expect(squareLabel('2026-08-20', thin, floor, 2)).toBe("Run 4 on 20 Aug 2026: 6 of 10 succeeded, under 70%, 4 failed, 2 read only in part, reused yesterday's list of sources");
    expect(runOutcome(thin, floor, 2)).toBe("6 of 10 succeeded, under 70%, 4 failed, 2 read only in part, reused yesterday's list of sources");
    expect(health(thin, floor)).toBe('red');
    // Held open by another run's failure: partial while failing nothing itself.
    const held = run({ n: 5, succeeded: 3, status: 'partial' });
    expect(squareLabel('2026-08-20', held, floor, 0)).toBe("Run 5 on 20 Aug 2026: 3 of 3 succeeded, another run's failed article was still missing");
    expect(runOutcome(held, floor, 0)).toBe("3 of 3 succeeded, another run's failed article was still missing");
    expect(health(held, floor)).toBe('amber');
    // A partial run that failed something itself says so by its count, not twice.
    const partial = run({ n: 6, succeeded: 9, failed: 1, status: 'partial' });
    expect(runOutcome(partial, floor, 0)).toBe('9 of 10 succeeded, 1 failed');
    expect(squareLabel('2026-08-20', partial, floor, 0)).toBe('Run 6 on 20 Aug 2026: 9 of 10 succeeded, 1 failed');
});
test('the chart and the squares share one slot a day, and a square fits inside it', () => {
    // The same arithmetic the bars are placed by: one equal slot a day between the
    // two margins, each day at its slot's middle.
    const slots = daySlots(1000, 4, { left: 40, right: 60 });
    expect(slots.slot).toBe(225);
    expect(slots.centres).toEqual([152.5, 377.5, 602.5, 827.5]);
    // A frame narrower than its own margins does not flip inside out.
    expect(daySlots(50, 3, { left: 40, right: 60 }).slot).toBe(0);
    // Eighty percent of the slot, held between the two limits a dense strip uses.
    expect(slotCellFor(10)).toEqual({ cell: 8, gap: 2 });
    expect(slotCellFor(40)).toEqual({ cell: 14, gap: 4 });
    expect(slotCellFor(4)).toEqual({ cell: 3, gap: 1 });
    // Under three pixels there is no square to draw here, and the caller draws the
    // scrolling strip instead.
    expect(slotCellFor(3.7)).toBeNull();
    expect(slotCellFor(0)).toBeNull();
});
