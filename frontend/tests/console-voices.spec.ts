import { test, expect } from './support/door-page';
import { reliabilityPublished, type SourceHealthView } from '../src/lib/server/payload';
import { whyChosen } from '../src/lib/console/voices/why-chosen';
/** A view the way the producer writes it today, built rather than read.
 *
 * Built, because the question is what the reader does with a shape no committed
 * file has to keep having. A fixture taken off the archive answers it until the
 * day the archive stops carrying that shape, and then it answers nothing while
 * still passing (`CLAUDE.md` section 13).
 */
function view(): SourceHealthView {
    return {
        generated_at: '2026-09-14T06:00:00Z',
        run_id: '2026-09-14-1',
        headline_sentence: 'Nothing on this page is outside its bound.',
        reliability_floor: 0.5,
        reliability_window_days: 30,
        min_complete_days: 30,
        complete_dates: 9,
        yield_readable: false,
        first_date: '2026-09-05',
        last_date: '2026-09-13',
        sources: [
            {
                source_id: 'canary-one',
                title: 'Canary One',
                vertical: 'ai',
                permission: 'allowed',
                availability: 'answering',
                retired: false,
                retired_on: null,
                opportunities: 12,
                publications: 9,
                source_failures: 1,
                reliability: 0.75,
                reliability_reads: 8
            }
        ]
    };
}
test('a view written before the ranking factor existed draws an absence, not a crash', () => {
    // The five reliability fields landed on 2026-09-14 and the committed view was
    // written by a run older than that, so on the day this row merged the file on
    // disk had none of them. A page that read `row.reliability.toFixed(3)` without
    // asking threw during prerender and took the whole route out of the build -
    // the census and the failure list with it, neither of which needs the field.
    //
    // The key is removed from a built view rather than counted in the committed
    // tree. A test that asserted "some committed view still lacks the field" goes
    // green today and red on the day the last old view ages out, which is a date
    // on the calendar rather than a change anybody made.
    expect(reliabilityPublished(view()), 'a current view reads as unpublished').toBe(true);
    const old = view() as Partial<SourceHealthView>;
    delete old.reliability_floor;
    delete old.reliability_window_days;
    delete old.headline_sentence;
    for (const row of old.sources ?? []) {
        delete (row as Partial<(typeof row)>).reliability;
        delete (row as Partial<(typeof row)>).reliability_reads;
    }
    expect(reliabilityPublished(old as SourceHealthView), 'a view from before the field reads as carrying it, so the page would draw a bar over nothing').toBe(false);
    // And the two states either side of the guard are distinguishable from
    // absence: no view at all is also false, and that is the state the panel was
    // already drawing an absence for.
    expect(reliabilityPublished(null)).toBe(false);
});

test('newest-day selection still counts the watchlist bonus without a separate catch view', () => {
    const chosen = whyChosen([{
        date: '2030-06-14', run_id: '2030-06-14-1', item_id: 'chosen', source_id: 'fixture-source',
        selection_score: 4, authority_score: 2, tier_score: 2, feed_weight: 1, feed_reliability: 1,
        recency_bonus: 1, lens_bonus: 0, watchlist_bonus: 0.5, carriage_step: 0.5
    }], 1);
    expect(chosen.drawn).toBe(1);
    expect(chosen.geometry).not.toBeNull();
    expect(chosen.records[0].facts).toEqual(expect.arrayContaining([
        expect.objectContaining({ label: 'Selection score', value: '4' }),
        expect.objectContaining({ label: 'Watchlist', value: '0.5' })
    ]));
});
