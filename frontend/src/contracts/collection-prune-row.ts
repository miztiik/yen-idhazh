// Generated from `backend/idhazh/contracts/collection_prune.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/** Why a pass stopped, which is what decides whether to run it again. */
export const STOP_REASON = ['exhausted', 'ceiling', 'failed'] as const;

export type StopReason = (typeof STOP_REASON)[number];

/** One pass, one row. */
export interface CollectionPruneRow {
	version?: string;

	/** The day the pass ran. */
	date: string;

	/** Which collection this pass walked. A word from a closed vocabulary - `prune.PrunableCollection` for what GitHub holds, a store name for what `state/` holds - and never a path. */
	collection: string;

	/** The oldest day a member could be created on and still qualify. Empty when the window has no lower end, which is what an age-based window means: everything older than the line qualifies, however old. */
	since?: string | null;

	/** The newest day a member could be created on and still qualify, inclusive. Empty when the window has no upper end. */
	until?: string | null;

	/** The ceiling in force. 0 is a survey: it reports the first member the window holds and takes nothing. */
	max_deletes_per_run: number;

	/** True when this pass was only reporting. Nothing was deleted. */
	dry_run: boolean;

	/** Members the listing yielded before the pass stopped. Never the size of the collection: a pass that stops on its ceiling stops listing too. */
	candidates_seen: number;

	/** Of those, how many the window held. The rest were the wrong age. */
	selected: number;

	/** How many this pass removed, or would have removed on a dry run. Never above the ceiling when the ceiling is above 0. */
	deleted: number;

	/** What those deletes freed, or would free. 0 is honest for a collection whose members have no size we can read - a workflow run's logs are one. */
	bytes_freed: number;

	/** Why the pass ended. */
	stopped_because: StopReason;

	/** The member the next pass begins at. Empty when the collection is exhausted, which is the one cell that says the backlog is cleared. */
	resume_from?: string | null;
}
