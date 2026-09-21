// Generated from `backend/idhazh/contracts/story_similarity_distribution.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/** One 0.001-wide slice of the band, and what the judge said inside it. */
export interface ScoreSlot {
	/** The slot's lower edge. A pair scoring exactly this lands in this slot; a pair scoring the upper edge lands in the next one. */
	bin_low: number;

	/** Agreed YES readings in this slot. */
	same_count?: number;

	/** Agreed NO readings. This is the count step 1 walks down and the only one that moves the line. */
	different_count?: number;

	/** Agreed UNCLEAR readings. Counted and never fitted on, so a rising share here is visible rather than silent. */
	unclear_count?: number;
}

/** The band, slot by slot, and the dates already counted into it. */
export interface StorySimilarityDistribution {
	version?: string;

	/** The lowest score the record holds a slot for. Below it nothing was ever judged, so the record can say nothing about it. */
	band_low: number;

	/** The top of the band. 1.00 is the highest a cosine goes, so the top slot is never short of room. */
	band_high: number;

	/** How wide each slot is. This is the resolution of the fitted line: the fit can only ever answer to the nearest slot edge. */
	bin_width: number;

	/** Which encoder produced the scores these counts were filed under. Null until the first day is counted. */
	scorer_model?: 'all-minilm-l6-v2-quantized' | null;

	/** What the cosine was worth for every count in this record. A different weight puts the same pair in a different slot, so a change archives the record rather than reinterpreting it. */
	cosine_weight?: number | null;

	/** What the key-point term was worth. Same reason as the cosine weight. */
	key_point_weight?: number | null;

	/** Which model produced these verdicts. Null until the first day is counted. */
	judge_model?: 'qwen3-5-9b-q4-k-m' | 'qwen3-5-9b-q4-k-m-thinking' | 'ornith-1-5-9b-q5-k-m' | 'gemma-4-e4b-it-qat-ud-q4-k-xl' | null;

	/** sha256 of the system turn the verdicts were produced under. */
	prompt_digest?: string | null;

	/** sha256 of the grammar the verdicts were produced under. */
	grammar_digest?: string | null;

	/** The sampler temperature every verdict in this record was decoded at. Null on a record written before the column existed, which is the one value it means: a sampler nobody recorded, not a sampler set to nothing. */
	judge_temperature?: number | null;

	/** Whether a reasoning span ran in front of every verdict counted here. A column of its own because no other column moves with it: an envelope moves only the prompt, which nothing here stamps. Without it a record counted cold and a record counted after reasoning are one population. */
	judge_thinks?: boolean | null;

	/** Every date already counted, sorted. A date already here is refused a second time rather than doubling its counts, which makes a re-run free instead of damaging. */
	counted_dates?: string[];

	/** Every date this judge has ever counted, sorted, and kept when an instrument move archives the counts. The counts are thrown away because they answer a different question afterwards; the fact that a night was read is not a count, so it stays. This is the list the outstanding-nights answer is taken from, and it holds every date in `counted_dates`. */
	judged_dates?: string[];

	/** The band, slot by slot, lowest first. Fixed size: the record never grows as the archive does, which is why the fit reads it and never the day tree (Guardrail #12). */
	slots: ScoreSlot[];
}
