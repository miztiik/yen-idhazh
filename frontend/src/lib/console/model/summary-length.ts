import type { Row } from '../../data/ledger';
import { runLengths } from './work';
import { median, number, textRows } from './rows';

export function summaryLength(rows: readonly Row[]) {
	return runLengths(textRows(rows)).map((run) => ({
		...run,
		median: median(rows.filter((row) => row.run_id === run.runId)
			.map((row) => number(row.summary_words)).filter((n): n is number => n !== null))!,
		compression: median(rows.filter((row) => row.run_id === run.runId)
			.map((row) => number(row.compression)).filter((n): n is number => n !== null))
	}));
}
