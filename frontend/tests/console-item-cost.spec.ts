/** Deterministic item cost rules over bounded fixtures; no browser, build, or layout matrix. */
import { expect, test } from '@playwright/test';
import { itemCost } from '../src/lib/console/item-cost';
const WINDOW = { start: '2026-08-01', end: '2026-08-31', days: 30 };
function row(cells: Record<string, string>): Record<string, string> {
    return { date: '2026-08-10', run_id: '2026-08-10-1', item_id: 'a-01', ...cells };
}
test.describe('what one item cost, as arithmetic', () => {
    test('an instrument that did not run is absent, and never a zero', () => {
        const cost = itemCost([
            row({ prefill_ms: '4000', decode_ms: '2000', input_tokens: '100', output_tokens: '10' }),
            row({ item_id: 'a-02', prefill_ms: '', decode_ms: '', input_tokens: '', output_tokens: '' })
        ], WINDOW);
        expect(cost.rows, 'both rows are in the window').toBe(2);
        expect(cost.timed, 'only one row carries both clocks').toBe(1);
        expect(cost.reading?.n).toBe(1);
        expect(cost.reading?.fastest, 'the empty cell became a zero').toBe(4000);
        expect(cost.counted, 'only one row carries a token count').toBe(1);
    });
    test('a zero IS a measurement, and it is counted', () => {
        const cost = itemCost([
            row({ input_tokens: '1000', cached_tokens: '0' }),
            row({ item_id: 'a-02', input_tokens: '1000', cached_tokens: '500' })
        ], WINDOW);
        expect(cost.readWhole, 'an item that reused nothing is not an item nobody measured').toBe(1);
        expect(cost.counted).toBe(2);
        expect(cost.reusedTokens).toBe(500);
        expect(cost.readTokens, '1000 read whole, plus the 500 the other one still read').toBe(1500);
        expect(cost.reusedPct).toBe(25);
        expect(cost.itemReusedPct).toBe(25);
    });
    test('a share of a window and the middle item are two different numbers', () => {
        const cost = itemCost([
            row({ input_tokens: '90000', cached_tokens: '0' }),
            row({ item_id: 'a-02', input_tokens: '1000', cached_tokens: '900' }),
            row({ item_id: 'a-03', input_tokens: '1000', cached_tokens: '900' })
        ], WINDOW);
        expect(cost.reusedPct, '1800 of the 91,800 tokens the window needed').toBe(2);
        expect(cost.itemReusedPct, 'the middle item reused 90 percent of its own prompt').toBe(90);
    });
    test('a rate is summed and then divided, never averaged over items', () => {
        const cost = itemCost([
            row({ prefill_ms: '1000', input_tokens: '10', cached_tokens: '0' }),
            row({ item_id: 'a-02', prefill_ms: '1000', input_tokens: '100', cached_tokens: '0' })
        ], WINDOW);
        expect(cost.msPerReadToken, '2000 ms over 110 tokens').toBeCloseTo(2000 / 110, 6);
    });
    test('cached tokens are taken out of the read count', () => {
        const cost = itemCost([row({ prefill_ms: '1000', input_tokens: '1000', cached_tokens: '900' })], WINDOW);
        expect(cost.readTokens).toBe(100);
        expect(cost.msPerReadToken, '1000 ms over the 100 it actually read').toBe(10);
    });
    test('whether the cache answered is a question about one call, not about the item', () => {
        const twoCalls = row({
            prefill_ms: '400872',
            input_tokens: '3886',
            cached_tokens: '1493',
            model_calls: '2',
            label_kind: 'label',
            label_prefill_ms: '214122',
            label_decode_ms: '88795',
            label_input_tokens: '1497',
            label_output_tokens: '205',
            label_cached_tokens: '0'
        });
        const oneCall = row({ item_id: 'a-02', input_tokens: '1000', cached_tokens: '0' });
        const cost = itemCost([twoCalls, oneCall], WINDOW);
        expect(cost.perCall, 'one of the two rows published a split').toBe(1);
        expect(cost.readWhole, 'both first calls read their prompt whole').toBe(2);
        expect(cost.reusedMedian, 'the middle of the two first calls, not of the totals').toBe(0);
        expect(cost.itemReusedPct, 'neither first call reused anything').toBe(0);
        expect(cost.reusedTokens).toBe(1493);
        expect(cost.readTokens, '2,393 the split item read, plus the 1,000 the other did').toBe(3393);
    });
    test('a row with no split still answers from the item total', () => {
        const cost = itemCost([
            row({ input_tokens: '1000', cached_tokens: '0', label_cached_tokens: '' }),
            row({ item_id: 'a-02', input_tokens: '1000', cached_tokens: '400' })
        ], WINDOW);
        expect(cost.perCall).toBe(0);
        expect(cost.readWhole).toBe(1);
        expect(cost.reusedMedian).toBe(200);
    });
    test('a middle taken over an even number of items is still a whole number', () => {
        const cost = itemCost([
            row({ input_tokens: '1687', output_tokens: '10', cached_tokens: '843' }),
            row({ item_id: 'a-02', input_tokens: '1688', output_tokens: '11', cached_tokens: '845' })
        ], WINDOW);
        expect(cost.promptTokens).toBe(1688);
        expect(cost.writtenTokens).toBe(11);
        expect(cost.itemReusedPct).toBe(50);
        expect(cost.reusedMedian).toBe(844);
    });
    test('a window with nothing in it draws nothing, rather than a chart of zeroes', () => {
        const cost = itemCost([row({ date: '2026-07-01', prefill_ms: '4000' })], WINDOW);
        expect(cost.rows).toBe(0);
        expect(cost.reading).toBeNull();
        expect(cost.writing).toBeNull();
        expect(cost.msPerReadToken).toBeNull();
        expect(cost.writeCostRatio).toBeNull();
    });
    test('a ratio against an absent rate is not a ratio', () => {
        const cost = itemCost([row({ prefill_ms: '1000', input_tokens: '100', cached_tokens: '0' })], WINDOW);
        expect(cost.msPerReadToken).not.toBeNull();
        expect(cost.msPerWrittenToken, 'nothing recorded a written token').toBeNull();
        expect(cost.writeCostRatio).toBeNull();
    });
});
