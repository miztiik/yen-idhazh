/** Does the native SQL syntax tree reference a table outside the explorer's schema? */

import { discoveryStatement } from './statement';

export async function checkTableSchemas(
	sql: string,
	query: (sql: string) => Promise<Record<string, unknown>[]>
): Promise<void> {
	// DuckDB serializes SELECT syntax, including DESCRIBE/SUMMARIZE, but not the EXPLAIN wrapper.
	const statement = discoveryStatement(sql);
	const [row] = await query(`SELECT json_serialize_sql('${statement.replaceAll("'", "''")}') AS syntax`);
	if (typeof row?.syntax !== 'string') throw new Error('The engine did not return parsed SQL.');
	const syntax: unknown = JSON.parse(row.syntax);
	if (syntax === null || typeof syntax !== 'object' || !('error' in syntax) || syntax.error !== false) {
		throw new Error('The engine could not inspect this SQL statement.');
	}
	const pending: unknown[] = [syntax];
	while (pending.length > 0) {
		const node = pending.pop();
		if (node === null || typeof node !== 'object') continue;
		if (Array.isArray(node)) { pending.push(...node); continue; }
		const fields = node as Record<string, unknown>;
		if ((fields.type === 'BASE_TABLE' || fields.type === 'SHOW_REF') &&
			((typeof fields.schema_name === 'string' && fields.schema_name !== '' && fields.schema_name !== 'main') ||
			 (typeof fields.catalog_name === 'string' && fields.catalog_name !== ''))) {
			throw new Error(`Table "${String(fields.table_name)}" uses an unavailable schema or database. Use its shown SQL table name.`);
		}
		pending.push(...Object.values(fields));
	}
}
