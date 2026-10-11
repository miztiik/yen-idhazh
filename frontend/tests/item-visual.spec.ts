import { expect, test } from '@playwright/test';
import { publishedVisualData, refusedVisualData } from '../src/lib/payload/drawing';
import { drawBars } from '../src/lib/visual/bar';
import type { VisualData } from '../src/lib/payload/types';
test.describe('what may not be drawn', () => {
    function compiled(): VisualData {
        return {
            version: '2026-09-13',
            renderer_version: '2026-09-13',
            item_id: 'energy-4821903756',
            type: 'bar',
            marks: ['A', 'B', 'C', 'D'].flatMap((name, index) => [
                { mark_id: `category-${index}`, text: name, value: null, unit: null, element_id: `name-${index}`, derived: null },
                { mark_id: `quantity-${index}`, text: null, value: String((index + 1) * 10), unit: 'MW', element_id: `value-${index}`, derived: null }
            ]),
            encoding: {
                category: [0, 1, 2, 3].map((index) => `category-${index}`),
                quantity: [0, 1, 2, 3].map((index) => `quantity-${index}`),
                quantity_x: [], time: [], series: [], size: [], bins: [], entity: [], event_label: []
            }
        };
    }
    test('the ordinary document is accepted, so the refusals below mean something', () => {
        const data = compiled();
        expect(refusedVisualData(data), 'a clean document was refused, so every case below is vacuous').toBeNull();
        expect(drawBars(data, 600).bars.length, 'a clean document drew no bar').toBeGreaterThan(0);
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
