// Generated from `backend/idhazh/contracts/similarity_holdout_pair.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/** One pair, two headlines, a person's mark and the reason for it. */
export interface SimilarityHoldoutPair {
	version?: string;

	/** One of the two articles, as a canonical URL. A person types this file, so it carries addresses rather than digests; the keys are recomputed on read. */
	left_url: string;

	/** The other article. */
	right_url: string;

	/** The digest date the left article was published on. On the row so a reader of the holdout report opens two named day files rather than searching the published tree for an address. */
	left_date: string;

	/** The digest date the right article was published on. The same day as the left one where the pair could ever have merged, and a different one where the pair straddled midnight. */
	right_date: string;

	/** The headline, so a reader of the holdout panel can tell which pair a mark belongs to. */
	left_title: string;

	/** The other headline. */
	right_title: string;

	/** True where the labeller judged the two to be one event. The false rows are the load-bearing ones: the line has to stay above every one of them. */
	same_story: boolean;

	/** When it was marked. A mark taken under an older reading of what counts as one story is still on record and still says when it was taken. */
	marked_on: string;

	/** Who marked it and why, in one line. A mark is worth what its labeller is worth, and one with no reason cannot be argued with later. */
	note: string;
}
