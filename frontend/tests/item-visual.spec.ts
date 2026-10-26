import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import { isVisualData, publishedVisualData, refusedVisualData, RENDERER_VERSION } from '../src/lib/payload/drawing';
import { drawBars, drawDots, drawLines, drawSlopes, statedBars, statedDots, statedLines, statedSlopes } from '../src/lib/visual/bar';
import { formatNumber, numberFormat, valueAxis } from './support/number-format';
import { frame } from '../src/lib/charts/frame';
import { drawScatter, statedScatter } from '../src/lib/visual/scatter';
import type { VisualData } from '../src/lib/payload/types';
import {
    chartConfig,
    storyChartGeometryConfig,
    type StoryChartGeometryConfig
} from '../src/lib/server/config';

const geometry = storyChartGeometryConfig();

test('story chart geometry projects the committed appearance settings', () => {
    const path = join(process.cwd(), '..', 'config', 'appearance.json');
    const appearance = JSON.parse(readFileSync(path, 'utf8')) as {
        chart: { story_geometry: StoryChartGeometryConfig };
    };
    expect(geometry).toEqual(appearance.chart.story_geometry);
});

function sourceCompiledChart(filename: string): VisualData {
    const path = join(
        process.cwd(),
        '..',
        'tests',
        'fixtures',
        'contracts',
        'visual-data',
        filename
    );
    const value: unknown = JSON.parse(readFileSync(path, 'utf8'));
    if (!isVisualData(value)) throw new Error(`${filename} is not a current compiled chart fixture`);
    return value;
}

function sourceQuantities(data: VisualData): number[] {
    return data.encoding.quantity.map((id) => {
        const mark = data.marks.find((candidate) => candidate.mark_id === id);
        if (mark?.value === null || mark?.value === undefined) throw new Error(`${id} has no quantity`);
        return Number(mark.value);
    });
}

test.describe('what may not be drawn', () => {
    test('scatter places every source entity and both quantities at narrow and wide widths', () => {
        const data = sourceCompiledChart('scatter-relationship.json');
        const fixtureRoot = join(process.cwd(), '..', 'tests', 'fixtures', 'visual-validator');
        const source = readFileSync(join(fixtureRoot, 'articles', 'scatter-relationship.txt'), 'utf8');
        const table = JSON.parse(readFileSync(
            join(fixtureRoot, 'tables', 'scatter-relationship.json'), 'utf8'
        )) as { elements: {
            element_id: string; entity: string; span_start: number; span_end: number;
            span_excerpt: string; value: string | null;
        }[] };
        const held = new Map(data.marks.map((mark) => [mark.mark_id, mark]));
        const sourceById = new Map(table.elements.map((element) => [element.element_id, element]));
        const facts = data.encoding.entity.map((id, index) => {
            const entity = sourceById.get(held.get(id)!.element_id!)!;
            const x = sourceById.get(held.get(data.encoding.quantity_x[index])!.element_id!)!;
            const y = sourceById.get(held.get(data.encoding.quantity[index])!.element_id!)!;
            expect(x.entity).toBe(entity.entity);
            expect(y.entity).toBe(entity.entity);
            for (const element of [entity, x, y]) {
                expect(source.slice(element.span_start, element.span_end)).toBe(element.span_excerpt);
            }
            return { label: entity.span_excerpt, x: Number(x.value), y: Number(y.value) };
        });
        const viewports = JSON.parse(readFileSync(
            join(fixtureRoot, 'viewports.json'), 'utf8'
        )) as { narrow: { width: number }; wide: { width: number } };
        expect(facts).toHaveLength(data.encoding.quantity.length);
        for (const room of [viewports.narrow.width, viewports.wide.width]) {
            const drawing = drawScatter(
                data, room, formatNumber, numberFormat, chartConfig().tick_density, geometry
            );
            expect(drawing.points).toHaveLength(facts.length);
            expect(drawing.width).toBe(room);
            expect(drawing.height).toBe(geometry.scatter_height_px);
            for (const [index, fact] of facts.entries()) {
                const point = drawing.points[index];
                expect(point.label).toBe(fact.label);
                expect(point.x).toBe(fact.x);
                expect(point.y).toBe(fact.y);
                const [x0, x1] = drawing.x.domain;
                const [y0, y1] = drawing.y.domain;
                expect(point.cx).toBeCloseTo(drawing.frame.left +
                    (fact.x - x0) / (x1 - x0) * drawing.frame.innerWidth, 8);
                expect(point.cy).toBeCloseTo(drawing.frame.bottom -
                    (fact.y - y0) / (y1 - y0) * drawing.frame.innerHeight, 8);
                expect(point.cx).toBeGreaterThanOrEqual(drawing.frame.left);
                expect(point.cx).toBeLessThanOrEqual(drawing.frame.right);
                expect(point.cy).toBeGreaterThanOrEqual(drawing.frame.top);
                expect(point.cy).toBeLessThanOrEqual(drawing.frame.bottom);
                expect(statedScatter(drawing)).toContain(
                    `${fact.label}: x ${fact.x} mw, y ${fact.y} gwh`
                );
            }
        }
    });
    test('scatter refuses incomplete pairs and non-finite values instead of filtering them', () => {
        for (const change of ['missing-x', 'missing-entity', 'non-finite', 'duplicate-entity']) {
            const data = sourceCompiledChart('scatter-relationship.json');
            if (change === 'missing-x') data.encoding.quantity_x.pop();
            if (change === 'missing-entity') data.encoding.entity.pop();
            if (change === 'non-finite') {
                data.marks.find((mark) => mark.mark_id === data.encoding.quantity_x[0])!.value = 'NaN';
            }
            if (change === 'duplicate-entity') {
                const first = data.marks.find((mark) => mark.mark_id === data.encoding.entity[0])!;
                data.marks.find((mark) => mark.mark_id === data.encoding.entity[1])!.element_id = first.element_id;
            }
            expect(refusedVisualData(data)).not.toBeNull();
        }
        const invalid = sourceCompiledChart('scatter-relationship.json');
        invalid.marks.find((mark) => mark.mark_id === invalid.encoding.quantity_x[0])!.value = 'NaN';
        expect(() => drawScatter(
            invalid, 390, formatNumber, numberFormat, chartConfig().tick_density, geometry
        )).toThrow('non-finite source pair');
    });
    function compiled(values: readonly number[] = [10, 20, 30, 40]): VisualData {
        return {
            version: '2026-10-25',
            renderer_version: RENDERER_VERSION,
            title: 'A comparison',
            caption: null,
            emphasized_mark_id: 'm3',
            item_id: 'energy-4821903756',
            type: 'bar',
            marks: ['A', 'B', 'C', 'D'].flatMap((name, index) => [
                { mark_id: `m${index * 2}`, text: name, time: null, value: null, unit: null, source_text: null, element_id: `name-${index}`, derived: null },
                { mark_id: `m${index * 2 + 1}`, text: null, time: null, value: String(values[index]), unit: 'MW', source_text: null, element_id: `value-${index}`, derived: null }
            ]),
            encoding: {
                category: [0, 1, 2, 3].map((index) => `m${index * 2}`),
                quantity: [0, 1, 2, 3].map((index) => `m${index * 2 + 1}`),
                quantity_x: [], time: [], series: [], size: [], bins: [], entity: [], event_label: []
            }
        };
    }
    test('the ordinary document is accepted, so the refusals below mean something', () => {
        const data = compiled();
        expect(refusedVisualData(data), 'a clean document was refused, so every case below is vacuous').toBeNull();
        expect(drawBars(data, 600, formatNumber, geometry).bars.length, 'a clean document drew no bar').toBeGreaterThan(0);
    });
    test('framing and one selected bar survive geometry without losing original figures', () => {
        const data = compiled();
        data.caption = '<script>not markup</script>';
        data.marks[3].source_text = '0.02 GW';
        const drawing = drawBars(data, 390, formatNumber, geometry);
        expect(drawing.title).toBe(data.title);
        expect(drawing.caption).toBe(data.caption);
        expect(drawing.bars.map((bar) => bar.emphasized)).toEqual([false, true, false, false]);
        expect(statedBars(drawing)).toContain('B 20 MW (highlighted) (source: 0.02 GW)');
        expect(statedBars(drawing)).toContain(data.caption);
    });
    test('narrow and wide drawings keep every mark inside the measured width without changing their readings', () => {
        const data = compiled();
        const narrow = drawBars(data, 360, formatNumber, geometry);
        for (const room of [360, 1440]) {
            const drawing = drawBars(data, room, formatNumber, geometry);
            expect(drawing.width).toBe(room);
            expect(drawing.height).toBe(narrow.height);
            expect(statedBars(drawing)).toBe(statedBars(narrow));
            expect(drawing.bars.map(({ name, stated, displayed, label, y, height }) =>
                ({ name, stated, displayed, label, y, height })
            )).toEqual(narrow.bars.map(({ name, stated, displayed, label, y, height }) =>
                ({ name, stated, displayed, label, y, height })
            ));
            for (const bar of drawing.bars) {
                expect(bar.width).toBeGreaterThanOrEqual(0);
                expect(bar.figure).toBeGreaterThan(bar.width);
                expect(bar.figure).toBeLessThan(drawing.width);
            }
            const fractional = drawBars(data, room + 0.75, formatNumber, geometry);
            expect(fractional).toEqual(drawing);
        }
    });
    test('digest and console display the same configured SI figure and retain the article wording', () => {
        for (const value of [1_000, 12_345, 1_234_567, 2_400_000, 8_900_000_000, 7_800_000_000_000]) {
            const drawing = drawBars(compiled([value, 20, 30, 40]), 600, formatNumber, geometry);
            const consoleAxis = valueAxis([0, value], frame(600, 220), {
                along: 'y', ticks: 4
            });
            for (const tick of consoleAxis.ticks.filter((tick) => tick.text !== '')) {
                const digestTick = drawBars(compiled([tick.value, 20, 30, 40]), 600, formatNumber, geometry);
                expect(digestTick.bars[0].displayed).toBe(tick.text);
            }
            expect(drawing.bars[0].displayed).toBe(formatNumber(value));
            expect(drawing.bars[0].stated).toBe(String(value));
            expect(statedBars(drawing)).toContain(`A ${value} MW`);
        }
    });
    test('dot positions rank source quantities on one common narrow and wide scale', () => {
        const data = sourceCompiledChart('dot-from-wind.json');
        const narrow = drawDots(data, 360, formatNumber, geometry);
        const wide = drawDots(data, 1440, formatNumber, geometry);
        expect(refusedVisualData(data)).toBeNull();
        expect(narrow.type).toBe('dot');
        const quantities = sourceQuantities(data);
        const ranked = quantities.map((value, index) => ({ value, index })).sort((a, b) => a.value - b.value);
        expect(ranked.map(({ index }) => narrow.dots[index].x)).toEqual(
            [...ranked.map(({ index }) => narrow.dots[index].x)].sort((a, b) => a - b)
        );
        const minimum = Math.min(...quantities);
        const maximum = Math.max(...quantities);
        for (const drawing of [narrow, wide]) {
            const plotStart = geometry.dot_radius_px;
            const valueX = Math.max(
                plotStart,
                drawing.width - Math.round(drawing.width * geometry.value_gutter_share)
            );
            const plotEnd = Math.max(plotStart, valueX - geometry.value_gap_px);
            expect(drawing.axisEnd).toBe(plotEnd);
            const domainStart = minimum === maximum ? minimum - 1 : minimum;
            const domainEnd = minimum === maximum ? maximum + 1 : maximum;
            for (const [index, value] of quantities.entries()) {
                const expectedX =
                    plotStart + ((value - domainStart) / (domainEnd - domainStart)) * (plotEnd - plotStart);
                expect(drawing.dots[index].x).toBeCloseTo(expectedX, 10);
            }
        }
        expect(narrow.dots.map(({ name, stated, displayed }) => ({ name, stated, displayed })))
            .toEqual(wide.dots.map(({ name, stated, displayed }) => ({ name, stated, displayed })));
        expect(narrow.height).toBe(wide.height);
        expect(narrow.dots.map((dot) => dot.name)).toEqual(['Denmark', 'Germany', 'Norway', 'Ireland']);
        expect(wide.dots[ranked[0].index].x).toBeLessThan(wide.dots[ranked.at(-1)!.index].x);
        expect(narrow.dots.every((dot) => dot.x - dot.radius >= 0 && dot.valueX < narrow.width)).toBe(true);
        expect(statedDots(narrow)).toContain('Germany 3400 mw');
    });
    test('slope lines preserve the paired source values between two named columns', () => {
        const data = sourceCompiledChart('slope-from-wind.json');
        expect(refusedVisualData(data)).toBeNull();
        const narrow = drawSlopes(data, 360, formatNumber, geometry);
        const wide = drawSlopes(data, 1440, formatNumber, geometry);
        expect(narrow.type).toBe('slope');
        expect(narrow.unit).toBe('mw');
        expect(narrow.leftLabel).toBe('2024');
        expect(narrow.rightLabel).toBe('2025');
        expect(narrow.slopes.map(({ name, left, right }) => [name, left.stated, right.stated]))
            .toEqual([['Denmark', '1200', '1500'], ['Germany', '2800', '3400']]);
        expect(wide.slopes.map(({ name, left, right }) => [name, left.stated, right.stated]))
            .toEqual(narrow.slopes.map(({ name, left, right }) => [name, left.stated, right.stated]));
        expect(narrow.leftX).toBeLessThan(narrow.rightX);
        expect(wide.leftX).toBeLessThan(wide.rightX);
        const quantities = sourceQuantities(data);
        const minimum = Math.min(...quantities);
        const maximum = Math.max(...quantities);
        for (const drawing of [narrow, wide]) {
            const top = geometry.slope_header_band_px;
            const bottom = drawing.height - geometry.slope_footer_band_px;
            for (const slope of drawing.slopes) {
                expect(slope.left.x).toBe(drawing.leftX);
                expect(slope.right.x).toBe(drawing.rightX);
                for (const point of [slope.left, slope.right]) {
                    expect(point.y).toBeGreaterThanOrEqual(geometry.slope_header_band_px);
                    expect(point.y).toBeLessThanOrEqual(
                        drawing.height - geometry.slope_footer_band_px
                    );
                }
            }
            for (const [index, value] of quantities.entries()) {
                const expectedY =
                    bottom + ((value - minimum) / (maximum - minimum)) * (top - bottom);
                const point = drawing.slopes[Math.floor(index / 2)][index % 2 === 0 ? 'left' : 'right'];
                expect(point.y).toBeCloseTo(expectedY, 10);
            }
        }
        expect(statedSlopes(narrow)).toContain('2024 1200');
        expect(statedSlopes(narrow)).toContain('2025 3400');
        expect(statedSlopes(narrow)).toContain('2024 1200 mw');
        expect(statedSlopes(narrow)).toContain('2025 1500 mw (highlighted)');
    });
    test('line geometry orders source readings by date and keeps every series value', () => {
        const data = sourceCompiledChart('line-from-wind.json');
        expect(refusedVisualData(data)).toBeNull();
        const narrow = drawLines(
            data, 360, formatNumber, numberFormat, chartConfig().tick_density, geometry
        );
        const wide = drawLines(
            data, 1440, formatNumber, numberFormat, chartConfig().tick_density, geometry
        );
        const readings = (drawing: ReturnType<typeof drawLines>) =>
            drawing.lines.map((line) => [
                line.name,
                line.points.map(({ timeLabel, stated, displayed }) => [timeLabel, stated, displayed])
            ]);
        expect(narrow.unit).toBe('mw');
        expect(readings(narrow)).toEqual([
            ['', [
                ['2023', '1200', formatNumber(1200)],
                ['2024', '1800', formatNumber(1800)],
                ['2025', '2400', formatNumber(2400)]
            ]]
        ]);
        expect(readings(wide)).toEqual(readings(narrow));
        expect(narrow.lines[0].points[0].x).toBeLessThan(narrow.lines[0].points[1].x);
        expect(narrow.lines[0].points[1].x).toBeLessThan(narrow.lines[0].points[2].x);
        expect(narrow.lines[0].dasharray).toBe(geometry.line_series_dash_arrays[0]);
        expect(statedLines(narrow)).toContain('2023 1200 mw');
        expect(statedLines(narrow)).toContain('2024 1800 mw (highlighted)');
    });
    test('multi-series line cues follow source order without relying on colour', () => {
        const data = sourceCompiledChart('line-multiple-series-from-wind.json');
        expect(refusedVisualData(data)).toBeNull();
        const drawing = drawLines(
            data, 360, formatNumber, numberFormat, chartConfig().tick_density, geometry
        );
        expect(drawing.lines.map((line) => line.name)).toEqual(['Denmark', 'Germany']);
        expect(drawing.lines.map((line) => line.dasharray)).toEqual(
            geometry.line_series_dash_arrays.slice(0, 2)
        );
    });
    test('the browser reader refuses repeated slope times and unnamed repeated lines', () => {
        const repeatedTime = sourceCompiledChart('slope-from-wind.json');
        const firstTime = repeatedTime.marks.find((mark) => mark.mark_id === repeatedTime.encoding.time[0]);
        const secondTime = repeatedTime.marks.find((mark) => mark.mark_id === repeatedTime.encoding.time[1]);
        if (firstTime === undefined || secondTime === undefined) throw new Error('slope fixture lacks time marks');
        secondTime.text = firstTime.text;
        expect(refusedVisualData(repeatedTime)).toContain('repeated slope time labels');

        const repeatedSeries = sourceCompiledChart('slope-from-wind.json');
        repeatedSeries.encoding.series = repeatedSeries.encoding.entity;
        repeatedSeries.encoding.entity = [];
        const firstSeries = repeatedSeries.marks.find((mark) => mark.mark_id === repeatedSeries.encoding.series[0]);
        const secondSeries = repeatedSeries.marks.find((mark) => mark.mark_id === repeatedSeries.encoding.series[1]);
        if (firstSeries === undefined || secondSeries === undefined) throw new Error('slope fixture lacks series marks');
        secondSeries.text = firstSeries.text;
        expect(refusedVisualData(repeatedSeries)).toContain('slope lines need distinct series labels');
    });
    test('the browser reader refuses a line without dates or with a repeated series date', () => {
        const invalidDate = sourceCompiledChart('line-from-wind.json');
        const time = invalidDate.marks.find(
            (mark) => mark.mark_id === invalidDate.encoding.time[0]
        );
        if (time === undefined) throw new Error('line fixture lacks its first time mark');
        time.time = 'not-a-date';
        expect(refusedVisualData(invalidDate)).toContain('invalid canonical date or year');

        const repeatedDate = sourceCompiledChart('line-from-wind.json');
        const first = repeatedDate.marks.find(
            (mark) => mark.mark_id === repeatedDate.encoding.time[0]
        );
        const third = repeatedDate.marks.find(
            (mark) => mark.mark_id === repeatedDate.encoding.time[2]
        );
        if (first === undefined || third === undefined) throw new Error('line fixture lacks a series date pair');
        third.time = first.time;
        expect(refusedVisualData(repeatedDate)).toContain('two readings for one series and date');
    });
    for (const [name, path] of [
        ['a walk out of the digest tree', 'digest/2026/08/20/../../../../etc/passwd'],
        ['an address somewhere else', 'https://example.invalid/x.json'],
        ['a file that is not a visual', 'digest/2026/08/20/ai.js'],
        ['the day payload itself', 'digest/2026/08/20/digest.json'],
        ['a date that is not one', 'digest/20xx/08/20/ai.json']
    ] as const) {
        test(`${name} is never asked for`, () => {
            // The path is about to be joined onto `base` and fetched. It came off a
            // committed payload rather than off the web and it is still matched
            // rather than trusted (Guardrail #11).
            expect(publishedVisualData(path), `${path} was accepted as a published visual`).toBe(false);
        });
    }
    test('a published marks path is recognised as one', () => {
        expect(publishedVisualData('digest/2026/08/20/energy-4821903756.json')).toBe(true);
    });
    for (const [name, breaks] of [
        ['the retired renderer', (data: VisualData) => { data.renderer_version = '2026-09-13'; }],
        ['emphasis on a category rather than a quantity', (data: VisualData) => { data.emphasized_mark_id = data.encoding.category[0]; }],
        ['emphasis on an absent mark', (data: VisualData) => { data.emphasized_mark_id = 'absent'; }],
        ['a duplicate mark id', (data: VisualData) => { data.marks.push(data.marks[0]); }],
        ['a non-finite figure', (data: VisualData) => { data.marks[1].value = 'Infinity'; }],
        [
            'a renderer this page does not know',
            (data: VisualData) => {
                data.renderer_version = '2099-01-01';
            }
        ],
        [
            'a type this page cannot draw',
            (data: VisualData) => {
                data.type = 'pie';
            }
        ],
        [
            'four names against three figures',
            (data: VisualData) => {
                data.encoding.quantity = data.encoding.quantity.slice(0, -1);
            }
        ],
        [
            'a channel naming a mark that is not carried',
            (data: VisualData) => {
                data.encoding.category = [...data.encoding.category.slice(1), 'm99'];
            }
        ],
        [
            'a bar with no figure',
            (data: VisualData) => {
                const drawn = data.marks.find((mark) => mark.value !== null);
                if (drawn)
                    drawn.value = null;
            }
        ],
        [
            'no marks at all',
            (data: VisualData) => {
                data.marks = [];
            }
        ]
    ] as const) {
        test(`${name} is refused rather than drawn`, () => {
            const data = compiled();
            breaks(data);
            expect(refusedVisualData(data), `${name} was accepted`).not.toBeNull();
        });
    }
    test('a document that is not one at all is refused', () => {
        expect(refusedVisualData(null)).not.toBeNull();
        expect(refusedVisualData('<svg/>')).not.toBeNull();
        expect(refusedVisualData([])).not.toBeNull();
    });
});
