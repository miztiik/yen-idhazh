import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
/**
 * `What the model did` is eleven measures, so it is eleven cards.
 *
 * The eleven-column table could not answer the question the operator brings to
 * it. A trend is a vertical scan, and in that table every column beside the one
 * being scanned was a different quantity; at thirty days it was 330 numbers and
 * eleven header paragraphs. The measures did not change and the words did not
 * change - only the container did, and the table is still here, one control
 * away.
 *
 * Two things this file protects that a screenshot cannot. The copy is
 * PROTECTED: all eleven labels ship verbatim, and a card that paraphrases one
 * fails. And every headline is the newest day's own cell, so a card cannot
 * quietly print a different day's figure from the row underneath it.
 */
const here = path.dirname(fileURLToPath(import.meta.url));
const frontend = path.resolve(here, '..');
/** The label set, read out of the page's own source.
 *
 * Parsed rather than typed in, because a constant typed into a test is a second
 * copy of the very strings the test exists to protect - and the second copy is
 * the one nobody updates.
 */
function columns(): {
    key: string;
    label: string;
    line: string;
    polarity: string;
}[] {
    const source = readFileSync(path.join(frontend, 'src', 'routes', 'console', 'model', '+page.svelte'), 'utf8');
    const start = source.indexOf('const COLUMNS');
    expect(start, 'the console page no longer names COLUMNS').toBeGreaterThan(-1);
    const block = source.slice(start, source.indexOf('\n\t];', start));
    // A label is single-quoted and holds no single quote; a line may be quoted
    // either way, because two of them hold an apostrophe. The polarity is
    // captured too: which way is better is declared beside the label, so a
    // column that lost it is a column that would paint from the sign again.
    const entry = /\{\s*key:\s*'([^']*)',\s*label:\s*'([^']*)',\s*line:\s*(?:'([^']*)'|"([^"]*)"),\s*polarity:\s*'([^']*)'\s*\}/g;
    return [...block.matchAll(entry)].map((match) => ({
        key: match[1],
        label: match[2],
        line: match[3] ?? match[4] ?? '',
        polarity: match[5]
    }));
}
test.describe('the eleven measures, as cards', () => {
    test('every column declares which way is the better way', async () => {
        // Not a colour assertion - console-polarity.spec.ts owns that. This is the
        // declaration: a column with no polarity would take the default and paint
        // neutral silently, which is the sign rule coming back as an omission.
        const wanted = columns();
        for (const column of wanted) {
            expect(['lower-is-better', 'higher-is-better', 'no-agreed-direction'], `${column.label} declares ${JSON.stringify(column.polarity)}`).toContain(column.polarity);
        }
        expect(wanted.filter((column) => column.polarity !== 'no-agreed-direction').length, 'no column has a direction any more, so every card paints neutral').toBeGreaterThan(0);
    });
});
