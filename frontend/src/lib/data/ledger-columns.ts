/** Which columns does a chosen ledger hold, whatever window a question selects? */

import { columnsOf, explainMissedFile, quoteIdent, readIndexes, serial, viewSource, viewStatement, type RawListedThrough } from './ask-reader';
import type { PageKeeper } from './page-keeper';
import { newestNamed } from './slice';
import { LOG_PREFIX } from './slice-reader';
import type { Column, LedgerName } from './slice-shapes';

/** The columns of the files a ledger's empty view reads: its newest listed raw day that has files,
 *  else the newest index entry that names a file, even one that holds no row. Columns belong to
 *  the ledger, not to a day, so this takes no window: it reads those files whatever days a
 *  question selects, and it moves no window. A ledger with no such file lists no column, and so
 *  does one whose indexes cannot be read, which a question over it names in its own answer. Files
 *  over `maxFetchBytes` are not fetched. Then, and when a file cannot be had or the engine cannot
 *  describe it, the ledger lists no column and the console gets one line that says why. */
export function readColumns(
	keeper: PageKeeper,
	ledger: LedgerName,
	maxFetchBytes: number,
	rawListed: RawListedThrough
): Promise<Column[]> {
	const none = (why: string): Column[] => {
		keeper.warn(`${LOG_PREFIX} ${ledger}: ${why}, so the column rail lists none of its columns`);
		return [];
	};
	return serial(async () => {
		const indexes = await readIndexes(keeper, ledger);
		if ('failed' in indexes) return [];
		const newestPacked = newestNamed(indexes.daily, indexes.monthly, indexes.yearly);
		const source = await viewSource(keeper, ledger, newestPacked, indexes, rawListed);
		if (source.files.length === 0) return [];
		const bytes = source.files.reduce((sum, file) => sum + file.bytes, 0);
		if (bytes > maxFetchBytes) {
			const paths = source.files.map((file) => file.path).join(', ');
			return none(`reading its columns would fetch ${bytes} bytes (${paths}), over the ${maxFetchBytes}-byte fetch ceiling`);
		}
		try {
			const holding = await keeper.hold(source.files);
			if ('failed' in holding) {
				const missed = source.files[holding.failed];
				return missed === undefined ? [] : none(explainMissedFile(missed, holding.shortfall));
			}
			try {
				await holding.engine.rows(viewStatement(ledger, holding.names.map((name) => ({ name, window: null })), true), []);
				return columnsOf(await holding.engine.rows(`DESCRIBE ${quoteIdent(ledger)}`, []));
			} finally {
				await holding.done();
			}
		} catch (error) {
			return none(`the query engine could not describe its newest file (${error instanceof Error ? error.message : String(error)})`);
		}
	});
}
