import { expect, test } from '@playwright/test';
import { bandFor, bandOutliers, bandPlacements, bandSpan, bandSplit, placeInBand, type CompressionPoint, type SummaryBand } from '../src/lib/charts/series';
test('the ladder is read the way the prompt reads it: the longest band an article reaches', () => {
    const ladder: SummaryBand[] = [
        { min_source_words: 0, target_words_min: 30, target_words_max: 45 },
        { min_source_words: 60, target_words_min: 50, target_words_max: 90 },
        { min_source_words: 700, target_words_min: 70, target_words_max: 150 }
    ];
    // `SummarizeConfig.band_for` picks the longest band the article reaches, and
    // the first rung starts at zero so every article lands in one. Two readings
    // of one ladder would put an article in one band on the page and another in
    // the prompt, with nothing on screen looking wrong.
    expect(bandFor(ladder, 0)).toEqual(ladder[0]);
    expect(bandFor(ladder, 59)).toEqual(ladder[0]);
    expect(bandFor(ladder, 60)).toEqual(ladder[1]);
    expect(bandFor(ladder, 699)).toEqual(ladder[1]);
    expect(bandFor(ladder, 700)).toEqual(ladder[2]);
    expect(bandFor(ladder, 90000)).toEqual(ladder[2]);
    // A config with no rungs places nothing, rather than placing everything in a
    // band it invented.
    expect(bandFor([], 400)).toBeNull();
    // The span each rung covers is read off the ladder, not off the rung: a rung
    // records the length it starts at, the next rung's floor is where it stops,
    // and the last one has no ceiling at all.
    expect(bandSpan(ladder, 0)).toBe('under 60');
    expect(bandSpan(ladder, 1)).toBe('60 to 699');
    expect(bandSpan(ladder, 2)).toBe('700 and over');
    // Grouped by hand, because `toLocaleString` reads the machine's locale.
    expect(bandSpan([{ min_source_words: 2000, target_words_min: 1, target_words_max: 2 }], 0)).toBe('2,000 and over');
});
test('a distance is the gap to the nearer bound, and inside the band it is zero', () => {
    const ladder: SummaryBand[] = [
        { min_source_words: 0, target_words_min: 30, target_words_max: 45 },
        { min_source_words: 60, target_words_min: 50, target_words_max: 90 }
    ];
    const point = (id: string, source: number, summary: number): CompressionPoint => ({
        date: '2026-08-28',
        item_id: id,
        source_words: source,
        summary_words: summary,
        truncation_flagged: false
    });
    expect(placeInBand(point('a', 400, 70), ladder)).toMatchObject({ place: 'inside', distance: 0 });
    // Both bounds are inclusive: a summary that hit the number it was asked for
    // is inside the band, not one word past it.
    expect(placeInBand(point('b', 400, 50), ladder)).toMatchObject({ place: 'inside', distance: 0 });
    expect(placeInBand(point('c', 400, 90), ladder)).toMatchObject({ place: 'inside', distance: 0 });
    expect(placeInBand(point('d', 400, 41), ladder)).toMatchObject({ place: 'short', distance: 9 });
    expect(placeInBand(point('e', 400, 260), ladder)).toMatchObject({ place: 'long', distance: 170 });
    // The article's own length picks the band, so the same summary is short in
    // one rung and inside in another.
    expect(placeInBand(point('f', 40, 45), ladder)).toMatchObject({ place: 'inside' });
    expect(placeInBand(point('g', 400, 45), ladder)).toMatchObject({ place: 'short', distance: 5 });
    expect(placeInBand(point('h', 400, 70), [])).toBeNull();
});
test('every day of the window gets a column, including the days that published nothing', () => {
    const ladder: SummaryBand[] = [
        { min_source_words: 0, target_words_min: 50, target_words_max: 90 }
    ];
    const window = { start: '2026-08-26', end: '2026-08-28' };
    const point = (date: string, id: string, summary: number): CompressionPoint => ({
        date,
        item_id: id,
        source_words: 400,
        summary_words: summary,
        truncation_flagged: false
    });
    const placed = bandPlacements([
        point('2026-08-26', 'a', 70),
        point('2026-08-26', 'b', 20),
        point('2026-08-28', 'c', 300),
        // Outside the window. A section that drew it would disagree with the
        // control the operator is looking at.
        point('2026-08-20', 'd', 70)
    ], ladder, window);
    expect(placed.map((one) => one.item_id)).toEqual(['a', 'b', 'c']);
    // The middle day published nothing and still gets a column. A chart drawn
    // only over the days that have rows closes the gap a missed day left, and a
    // missed day is a fact the operator came here to see.
    expect(bandSplit(placed, window)).toEqual([
        { date: '2026-08-26', inside: 1, short: 1, long: 0, items: 2 },
        { date: '2026-08-27', inside: 0, short: 0, long: 0, items: 0 },
        { date: '2026-08-28', inside: 0, short: 0, long: 1, items: 1 }
    ]);
    // Worst first, and the inside rows are not outliers at all.
    const worst = bandOutliers(placed);
    expect(worst.map((one) => one.item_id)).toEqual(['c', 'b']);
    expect(worst.map((one) => one.distance)).toEqual([210, 30]);
});
test('two equal misses rank in a fixed order, so the page cannot move between builds', () => {
    const ladder: SummaryBand[] = [
        { min_source_words: 0, target_words_min: 50, target_words_max: 90 }
    ];
    const window = { start: '2026-08-26', end: '2026-08-28' };
    const point = (date: string, id: string, source: number): CompressionPoint => ({
        date,
        item_id: id,
        source_words: source,
        summary_words: 120,
        truncation_flagged: false
    });
    // Three articles 30 words past the same band. The longer article breaks the
    // tie, then the date, then the id - never the order they arrived in.
    const placed = bandPlacements([point('2026-08-28', 'zzz', 400), point('2026-08-26', 'aaa', 400), point('2026-08-27', 'mid', 900)], ladder, window);
    expect(bandOutliers(placed).map((one) => one.item_id)).toEqual(['mid', 'aaa', 'zzz']);
    expect(bandOutliers([...placed].reverse()).map((one) => one.item_id)).toEqual([
        'mid',
        'aaa',
        'zzz'
    ]);
});
