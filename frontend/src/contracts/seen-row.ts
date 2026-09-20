// Generated from `backend/idhazh/contracts/seen.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * One row of `state/seen/<YYYY>/<MM>/<DD>.csv`, appended the first time an address
 * is a candidate.
 *
 * It carries no address, for the reason `PublishedRow` carries none: nothing on
 * the read path opens one. `ledger.load_seen` reads `url_key` and
 * `first_seen_at` and returns a map of the two.
 *
 * `first_seen_run` is what says which file the row lives in. A run id is
 * `<date>-<n>`, so its first ten characters are the run's digest date, which is
 * the date `ledger.append_seen` files by. `first_seen_at` is a wall clock and
 * crosses midnight independently of the run it belongs to, so it names the day
 * a row was written and not the day the row is filed under.
 */
export interface SeenRow {
	version?: string;

	url_key: string;

	first_seen_at: string;

	first_seen_run: string;
}
