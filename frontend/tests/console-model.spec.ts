/** The protected card vocabulary and its declared polarity, without a presentation matrix. */
import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { cardColumns } from '../src/lib/console/model/cards';
import { CONSOLE_MODEL_LABELS_PAGE } from '../scripts/doc-test-inputs';

test('every column declares which way is the better way', () => {
    for (const column of cardColumns) {
        expect(['lower-is-better', 'higher-is-better', 'no-agreed-direction'], `${column.label} declares ${JSON.stringify(column.polarity)}`).toContain(column.polarity);
    }
    expect(cardColumns.filter((column) => column.polarity !== 'no-agreed-direction').length,
        'no column has a direction any more, so every card paints neutral').toBeGreaterThan(0);
});

test('the eleven original card labels and explanations remain verbatim beside the twelfth card', () => {
    const document = readFileSync(resolve('..', CONSOLE_MODEL_LABELS_PAGE), 'utf8');
    const start = document.indexOf('| Label | The line under it |');
    expect(start).toBeGreaterThan(-1);
    const rows: { label: string; line: string }[] = [];
    for (const row of document.slice(start).split('\n').slice(2)) {
        if (!row.startsWith('|')) break;
        const cells = row.split('|').slice(1, -1).map((cell) => cell.trim());
        rows.push({ label: cells[0], line: cells[1] === '-' ? '' : cells[1] });
    }
    expect(rows).toHaveLength(11);
    expect(cardColumns).toHaveLength(12);
    expect(cardColumns.slice(0, 11).map(({ label, line }) => ({ label, line }))).toEqual(rows);
    expect(cardColumns[11]).toMatchObject({ key: 'determinism', polarity: 'no-agreed-direction' });
});
