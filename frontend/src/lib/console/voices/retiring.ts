/** Which source squares support the producer's retirement countdown? */
import type { Retiring } from '../../server/source-retiring';
import { axisLabels, denseCellFor, ROW_STRIP_PX } from '../../charts/run-history';
import { factsOf, recordsOf } from '../../charts/readout';
import { shortDate } from '../../format';
export function retirementDrawing(strip: Retiring | null, density: number) {
	const dates = strip?.dates ?? [];
	const cell = denseCellFor(ROW_STRIP_PX, dates.length);
	const squares = strip === null ? [] : [...strip.rows, ...strip.unjudged].flatMap((row) => row.squares.map((square) => ({ sourceId: row.sourceId, square })));
	return {
		cell, axis: axisLabels(dates, { density, pitch: cell.cell + cell.gap }),
		index: new Map(squares.map((one, index) => [`${one.sourceId}|${one.square.date}`, index])),
		records: recordsOf(squares.map((one) => factsOf(`${one.sourceId}, ${shortDate(one.square.date)}`, [{ label: 'That day', value: one.square.label }], 'nothing on record'))),
		resting: Math.max(0, ((strip?.rows[0] ?? strip?.unjudged[0])?.squares.length ?? 0) - 1)
	};
}
