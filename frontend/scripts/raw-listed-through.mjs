/** Which newest raw day listing did the site build stage for each ledger? */

import { existsSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

export function rawListedThrough(staticRoot = 'frontend/static') {
	const raw = join(staticRoot, 'state', 'raw');
	if (!existsSync(raw)) return {};
	/** @type {Record<string, string>} */
	const result = {};
	for (const ledger of readdirSync(raw, { withFileTypes: true })) {
		if (!ledger.isDirectory()) continue;
		const index = join(raw, ledger.name, 'index');
		if (!existsSync(index)) continue;
		const days = readdirSync(index)
			.filter((name) => /^\d{4}-\d{2}-\d{2}\.json$/.test(name))
			.map((name) => name.slice(0, -5))
			.sort();
		if (days.length > 0) result[ledger.name] = days[days.length - 1];
	}
	return result;
}
