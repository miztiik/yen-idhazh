/** Two independent clocks, and rates only where both halves were recorded. */
import type { Row } from '../../data/ledger';
import { distribution } from '../../charts/series';
import { finiteCell, nearestRank } from '../rates';

export function nativeItemCost(rows: readonly Row[]) {
	const readings = (cell: string) => rows.flatMap((row) => {
		const value = finiteCell(row[cell]);
		return value === null || value < 0 ? [] : [value];
	});
	const reading = distribution(readings('prefill_ms'));
	const writing = distribution(readings('decode_ms'));
	let readMs = 0;
	let readTokens = 0;
	let writeMs = 0;
	let writeTokens = 0;
	let readPairs = 0;
	let writePairs = 0;
	for (const row of rows) {
		const input = finiteCell(row.input_tokens);
		const cache = finiteCell(row.cached_tokens);
		const prefill = finiteCell(row.prefill_ms);
		const output = finiteCell(row.output_tokens);
		const decode = finiteCell(row.decode_ms);
		if (input !== null && cache !== null && cache >= 0 && input > cache && prefill !== null && prefill >= 0) {
			readMs += prefill; readTokens += input - cache; readPairs += 1;
		}
		if (output !== null && output > 0 && decode !== null && decode >= 0) {
			writeMs += decode; writeTokens += output; writePairs += 1;
		}
	}
	const msPerReadToken = readPairs === 0 ? null : readMs / readTokens;
	const msPerWrittenToken = writePairs === 0 ? null : writeMs / writeTokens;
	const bins = [reading, writing].flatMap((times) => times === null ? [] : times.bins);
	const domain: [number, number] | undefined = bins.length === 0 ? undefined : [
		Math.min(...bins.map((bin) => bin.from === 0 ? bin.to / 2 : bin.from)),
		Math.max(...bins.map((bin) => bin.to))
	];
	return {
		rows: rows.length, reading, writing, domain, readPairs, writePairs, msPerReadToken, msPerWrittenToken,
		writeCostRatio: msPerReadToken === null || msPerReadToken <= 0 || msPerWrittenToken === null
			? null : msPerWrittenToken / msPerReadToken,
		promptTokens: nearestRank(readings('input_tokens'), 0.5),
		writtenTokens: nearestRank(readings('output_tokens'), 0.5),
		unknownCache: rows.filter((row) => finiteCell(row.input_tokens) !== null && finiteCell(row.cached_tokens) === null).length
	};
}
