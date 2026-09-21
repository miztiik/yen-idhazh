// Generated from `backend/idhazh/contracts/council_shard_outcome.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/** The three ways one unit of hosted work ends. */
export const SHARD_OUTCOME = ['completed', 'stopped_on_deadline', 'nothing_to_do'] as const;

export type ShardOutcome = (typeof SHARD_OUTCOME)[number];

/** One unit of council work: how it ended, what it cost, and who it hosted. */
export interface CouncilShardOutcome {
	version?: string;

	/** The digest date this run judged. */
	date: string;

	/** The council run, minted from the day the council ran. */
	run_id: string;

	/** Which tenant this unit hosted. Without it a night running two tenants files rows nobody can attribute. Recorded rather than validated: there is no membership check, because the council records who ran and never declares who may exist. The value arrives from the tenant's own module constant, so a typo is a source edit a reviewer sees. */
	judge_id: string;

	/** Which unit of the split this row is about. Two values below zero are reserved for the units that run once a date rather than once a shard: -1 picked the work and -2 counted what came back. Without them a run whose count died would leave no row saying so. */
	shard: number;

	/** How many units the work was split across. A run reporting fewer rows than this left work unread, and the pair alone says so. The two reserved units carry the run's real width, so one date's rows all agree. */
	shards: number;

	/** How the unit ended. A unit killed by the platform writes no row at all, and absence against the recorded count is what says so. */
	outcome: ShardOutcome;

	/** When the unit began. */
	started_at: string;

	/** Wall clock for the unit of work. Not the job: the job's own clock includes a checkout and a weights restore this row is not about, and those are recorded where the job is. */
	seconds_spent: number;

	/** How many calls the hosted work made. Empty, not zero, for a tenant that runs no model - zero would read as a model that answered nothing. One call, one count, derived from no other column. */
	model_calls?: number | null;

	/** Prompt tokens the server reported across the unit. */
	tokens_in?: number | null;

	/** Generated tokens the server reported across the unit. */
	tokens_out?: number | null;

	/** Wall clock inside model calls. Read against `seconds_spent`, the two say how much of a unit was the model and how much was everything else. */
	model_seconds?: number | null;

	/** The processor name, one line read from the kernel's own file. Without it a slow night and a slower processor read identically, and there is no join key onto what already characterises the runner pool. */
	host_model?: string | null;
}
