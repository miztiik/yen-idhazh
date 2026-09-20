// Generated from `backend/idhazh/contracts/corpus.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/** The three turns of one supervised sample, in the order a trainer reads them. */
export const CHAT_ROLE = ['system', 'user', 'assistant'] as const;

export type ChatRole = (typeof CHAT_ROLE)[number];

/** One turn. `content` is text and never a structure, because that is what a trainer reads. */
export interface ChatTurn {
	role: ChatRole;

	content: string;
}

/** One article's exchange, as one line of `corpus/corpus.jsonl`. */
export interface CorpusRow {
	version?: string;

	/** The training column, and the only one a trainer reads. System, user, assistant, in that order. */
	messages: ChatTurn[];

	/** Deduplication, and what the holdout file is a set of. */
	url_key: string;

	/** The run day. It drives the roll's eviction and the date-based holdout split. */
	date: string;

	/** Which model wrote the assistant turn. A distilled corpus mixes rows from two teachers and nothing else on the row tells them apart. */
	model_id: string;

	/** The one diversity column a quota can act on. Measured 2026-08-27 over the 114 published items of that day: present on 114 of 114, where events reached 58 percent, entities 53 and lenses 34. */
	vertical: string;
}
