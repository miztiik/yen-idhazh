// Generated from `backend/idhazh/contracts/corpus.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * What the window holds, and when each of its two schedules last fired.
 *
 * Committed beside the rows, and it is the schedule itself rather than a
 * report about one. `on.schedule` is parsed before any step runs, so no value
 * in `config/` can ever reach a cron line; a cadence that has to be
 * configurable is therefore a due-check in a step, and a due-check needs
 * durable state to compare against. That state is this file.
 *
 * Keeping it as dates rather than as timestamps is deliberate: a due-check
 * that compares two `YYYY-MM-DD` strings is a test with no clock in it, and
 * when the job actually ran is already recorded by the commit it made.
 */
export interface CorpusMeta {
	version?: string;

	/** How many lines `corpus.jsonl` holds. */
	rows?: number;

	/** The oldest run day in the window. None when it is empty. */
	first_date?: string | null;

	/** The newest run day in the window. */
	last_date?: string | null;

	/** Rows per vertical. What a diversity quota reads. */
	verticals?: Record<string, number>;

	/** Rows per model that wrote the assistant turn. A mixed corpus has two. */
	models?: Record<string, number>;

	/** The digest day the last harvest read. The harvest step compares it against the day it is running for, so a missed day self-corrects on the next wake. */
	harvested_date?: string | null;

	/** The day `prune.yml` last squashed history. It is the only thing that stops a due-check from firing every day once the repository is older than `finetune.prune_keep_days`. */
	pruned_date?: string | null;

	/** sha256 over `summarize.prompt_inputs` at harvest time - the template plus every number substituted into it. Not derivable from the rows, which carry rendered prompts rather than the template, and it is what tells a person that the prompt moved under the corpus they are about to train on. */
	prompt_digest?: string | null;
}
