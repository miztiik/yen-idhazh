/** What do reading and writing cost for the same recorded amount of work? */

/** The ledger reports milliseconds; the old throughput caller prints tokens a second. */
const MS_PER_SECOND = 1000;

function measured(value: string | undefined): number | null {
	if (value === undefined || value === '') return null;
	const parsed = Number(value);
	return Number.isFinite(parsed) ? parsed : null;
}

/** The existing server caller's two independent rates, including its absent-cache behavior. */
export function itemRates(row: Record<string, string>): {
	read: number | null;
	write: number | null;
} {
	const prefillMs = measured(row.prefill_ms);
	const decodeMs = measured(row.decode_ms);
	const prompt = measured(row.input_tokens);
	const written = measured(row.output_tokens);
	const evaluated = prompt === null ? null : prompt - (measured(row.cached_tokens) ?? 0);
	return {
		read:
			prefillMs !== null && prefillMs > 0 && evaluated !== null && evaluated > 0
				? evaluated / (prefillMs / MS_PER_SECOND)
				: null,
		write:
			decodeMs !== null && decodeMs > 0 && written !== null && written > 0
				? written / (decodeMs / MS_PER_SECOND)
				: null
	};
}
