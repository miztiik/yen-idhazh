import { expect, test } from '@playwright/test';
import { chartFlow, type FlowDay } from '../src/lib/console/pipelines/drawing-flow';
/** A flow whose four stages fall and whose three losses are all non-zero. */
const DAYS: FlowDay[] = [
    { reached: 1000, asked: 700, drafted: 100, published: 80 },
    { reached: 500, asked: 300, drafted: 50, published: 40 }
];
test('the stepped list is the same flow the diagram draws', () => {
    // One call, two shapes. Two functions over one ledger is how two pictures of
    // it drift, and the drift is invisible because each looks right alone.
    const { steps } = chartFlow(DAYS);
    expect(steps.map((step) => step.label)).toEqual([
        'Reached',
        'Asked the model',
        'Drafted',
        'Published'
    ]);
    expect(steps.map((step) => step.value)).toEqual([1500, 1000, 150, 120]);
    // Shares are of everything that reached chart drawing, which is what the diagram's
    // own labels print.
    expect(steps.map((step) => step.share)).toEqual([100, 67, 10, 8]);
    expect(steps.map((step) => step.lost?.label ?? null)).toEqual([
        'Answered without a visual',
        'The model drew nothing',
        'Did not survive the checks',
        null
    ]);
    // What leaves a stage is what arrived at it. The list has to conserve for
    // the same reason the diagram does: a branch that does not is a shape, not
    // the data.
    for (const [index, step] of steps.entries()) {
        const next = steps[index + 1];
        if (next === undefined) {
            expect(step.lost, 'the last stage is where items stop').toBeNull();
            continue;
        }
        expect(next.value + (step.lost?.value ?? 0), `${step.label} does not conserve`).toBe(step.value);
    }
});
test('a branch of zero is no branch in the list either', () => {
    // A loss too small to see and no loss at all are two different facts, and a
    // row reading `0 (0%)` is the first one.
    const { steps } = chartFlow([{ reached: 10, asked: 10, drafted: 4, published: 4 }]);
    expect(steps.map((step) => step.lost?.label ?? null)).toEqual([
        null,
        'The model drew nothing',
        null,
        null
    ]);
});
test('a window with no flow to draw has no list to draw either', () => {
    // Both empty states, so a narrow column gets the sentence rather than an
    // empty list where the diagram would have said why.
    const nothing = chartFlow([{ reached: 0, asked: 0, drafted: 0, published: 0 }]);
    expect(nothing.empty).toBe(true);
    expect(nothing.steps).toEqual([]);
    const gained = chartFlow([{ reached: 100, asked: 60, drafted: 5, published: 9 }]);
    expect(gained.empty).toBe(true);
    expect(gained.steps).toEqual([]);
});
