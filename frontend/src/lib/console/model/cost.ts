import type { Row } from '../../data/ledger';
import { distribution } from '../../charts/series';
import { number } from './rows';

export function cost(rows: readonly Row[], column: 'summarize_ms' | 'score_ms') {
	const readings = rows.map((row) => number(row[column]));
	// Native clocks historically used zero for an unmeasured score clock.
	const values = readings.filter((n): n is number => n !== null && n > 0);
	return { times: distribution(values), untimed: readings.length - values.length };
}
