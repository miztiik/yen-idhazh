import type { Row } from '../../data/ledger';
import type { SummaryBand } from '../../server/config';
import { modelSwap } from './work';
import { textRows } from './rows';

export function modelChange(scores: readonly Row[], items: readonly Row[], bands: readonly SummaryBand[], minimum: number) {
	// The two populations meet only at the dated boundary, never by item or run.
	return modelSwap(textRows(scores), textRows(items), bands, minimum);
}
