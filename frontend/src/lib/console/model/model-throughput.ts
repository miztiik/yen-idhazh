import type { Row } from '../../data/ledger';
import { modelByDate, throughputWithin } from './work';
import { textRows } from './rows';
import { itemRates, nearestRank } from '../rates';

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
	return throughputWithin(dated, modelByDate(text), window).map((day) => {
		const rates = dated.get(day.date)!.map(itemRates);
		const band = (key: 'read' | 'write') => {
			const values = rates.map((rate) => rate[key]!);
			return { min: Math.min(...values), max: Math.max(...values),
				median: nearestRank(values, 0.5)!, p25: nearestRank(values, 0.25)!, p75: nearestRank(values, 0.75)! };
		};
		return { ...day, read: band('read'), write: band('write') };
	});
}
