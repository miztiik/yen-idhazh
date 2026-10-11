import type { Row } from '../../data/ledger';
import { modelByDate, throughputWithin } from './work';
import { textRows } from './rows';
import { itemRates } from '../rates';

export function modelThroughput(rows: readonly Row[], window: { start: string; end: string }) {
	const text = textRows(rows).filter((row) => {
		const rate = itemRates(row);
		return rate.read !== null && rate.write !== null;
	});
	const dated = new Map<string, Record<string, string>[]>();
	for (const row of text) {
		const group = dated.get(row.date) ?? [];
		group.push(row);
		dated.set(row.date, group);
	}
	return throughputWithin(dated, modelByDate(text), window);
}
