import type { Row } from '../../data/ledger';
import { distribution } from '../../charts/series';
import { number } from './rows';
import { nearestRank } from '../rates';

export function cost(rows: readonly Row[], column: 'summarize_ms' | 'score_ms') {
	const readings = rows.map((row) => number(row[column]));
	// Native clocks historically used zero for an unmeasured score clock.
	const values = readings.filter((n): n is number => n !== null && n > 0);
	const times = distribution(values);
	return { times: times === null ? null : {
		...times, median: nearestRank(values, 0.5)!, p95: nearestRank(values, 0.95)!
	}, untimed: readings.length - values.length };
}
