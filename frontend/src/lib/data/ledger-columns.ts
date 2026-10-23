/** Which columns can the current question safely fetch before Run? */

import { columnsOf, createOwnedView, dropOwnedViews, explainMissedFile, planQuestion, preflight, quoteIdent, serial } from './ask-reader';
import type { PageKeeper } from './page-keeper';
import { LOG_PREFIX } from './slice-reader';
import type { Column, DateStamp, LedgerName } from './slice-shapes';

/** Price the whole selection before fetching even one ledger's column source. */
export function readColumns(keeper: PageKeeper, ledgers: readonly LedgerName[], from: DateStamp, to: DateStamp, maxFetchBytes: number, maxFiles: number): Promise<Column[]> {
	return serial(async () => {
		const planned = await planQuestion(keeper, ledgers, from, to);
		if ('state' in planned) {
			keeper.warn(`${LOG_PREFIX} column rail: ${JSON.stringify(planned)}`);
			return [];
		}
		const refusal = preflight(planned.cost, maxFiles, maxFetchBytes);
		if (refusal !== null) {
			keeper.warn(`${LOG_PREFIX} column rail: ${JSON.stringify(refusal)}`);
			return [];
		}
		const columns: Column[] = [];
		for (const one of planned.ledgers) {
			if (one.emptySource.length === 0) continue;
			const files = one.emptySource.map((source) => source.file);
			try {
				const holding = await keeper.hold(files);
				if ('failed' in holding) {
					keeper.warn(`${LOG_PREFIX} ${one.ledger}: ${explainMissedFile(files[holding.failed], holding.shortfall)}; no columns listed`);
					continue;
				}
				try {
					await dropOwnedViews(holding.engine);
					await createOwnedView(holding.engine, one.ledger, holding.names.map((name) => ({ name, window: null })), true);
					columns.push(...columnsOf(await holding.engine.rows(`DESCRIBE ${quoteIdent(one.ledger)}`, [])).map((column) => ({ ...column, name: `${one.ledger}.${column.name}` })));
				} finally {
					await dropOwnedViews(holding.engine);
					await holding.done();
				}
			} catch (error) {
				keeper.warn(`${LOG_PREFIX} ${one.ledger}: the query engine could not describe its compact file (${String(error)})`);
			}
		}
		return columns;
	});
}
