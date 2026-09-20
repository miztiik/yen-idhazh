// Generated from `backend/idhazh/contracts/observation_index.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/** One row of `state/score-index/<YYYY>/<MM>/<DD>.csv`: one measurement already held. */
export interface ObservationIndexRow {
	version?: string;

	observation_digest: string;
}
