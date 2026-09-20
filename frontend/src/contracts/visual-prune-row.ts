// Generated from `backend/idhazh/contracts/visual_prune.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/** One cleanup pass, one row. */
export interface VisualPruneRow {
	version?: string;

	/** The digest date the cleaning run was for. */
	date: string;

	/** The run that did the cleaning. */
	run_id: string;

	/** `retention.image_months` in force. -1 means no age window at all, so the row reports and nothing is ever a candidate; it is the model default and was what shipped until 2026-09-13, when config/idhazh.json took 13. */
	policy_months: number;

	/** `retention.max_deletes_per_run` in force - the fuse. */
	max_deletes_per_run: number;

	/** True when this run was only reporting. Set by config or by the step's own flag, and either one is enough. */
	dry_run: boolean;

	/** The day the policy drew its line at. Empty when the policy is off, because a disabled policy has no line and a stand-in date would read like one. */
	cutoff_date?: string | null;

	/** Rendered visuals older than the cutoff. The whole backlog. */
	candidates_found: number;

	/** How many this run removed. Always 0 on a dry run. */
	deleted: number;

	/** Candidates the fuse would not let this run reach. The same fact on a dry run as on a live one, which is what stops it collapsing into `deleted`. */
	skipped_by_fuse: number;

	/** Whether the backlog was larger than the fuse. */
	fuse_tripped: boolean;

	/** What the deletions freed, measured. 0 on a dry run. */
	bytes_reclaimed: number;

	/** The oldest published day still carrying a rendered visual after this run. Empty when the tree carries none at all. Read against `cutoff_date`, it says whether the policy has caught up. */
	oldest_kept?: string | null;

	/** The committed payload tree under `frontend/public/digest/`, before the run. Never the built site - two trees, and one cannot stand in for the other. */
	payload_bytes_before: number;

	/** The same tree, after the run. */
	payload_bytes_after: number;
}
