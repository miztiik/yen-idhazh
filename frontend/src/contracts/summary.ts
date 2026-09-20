// Generated from `backend/idhazh/contracts/summary.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * One model call's own five numbers.
 *
 * Nested rather than flattened because the same five have to be described once
 * and checked once. The two CSV ledgers cannot nest, so they spell these names
 * with a `label_`/`summary_` prefix and `idhazh.telemetry` is the one place
 * that flattens - one translator, against one copy of this validator per
 * contract that would otherwise carry it.
 */
export interface CallCost {
	kind: CallKind;

	/** Milliseconds this call spent reading its prompt. A duration and never a rate: a prompt token costs more the deeper into the context it sits, so dividing this by the tokens the call evaluated gives a figure that cannot be compared with another call's. */
	prefill_ms?: number;

	/** Milliseconds this call spent writing its reply. */
	decode_ms?: number;

	/** Prompt tokens, cached part included. */
	input_tokens?: number;

	/** Tokens this call wrote. */
	output_tokens?: number;

	/** Prompt tokens the runtime reused instead of reading. Zero is a real answer and means the slot was cold; `input_tokens` minus this is what `prefill_ms` paid for. */
	cached_tokens?: number;
}

/**
 * Which model call these numbers came from.
 *
 * Four members and not two, because the call structure moves under this
 * vocabulary rather than beside it. `summarize` and `visual_plan` are what the
 * pipeline dispatches today, on two different models in two different jobs.
 * `label` and `summarize_and_plan` are the pair `idhazh.classify.calls` builds,
 * which lands behind a flag first and then becomes the only pair. A reading
 * that spans the flip needs all four names, or the step change in every series
 * reads as a regression rather than as the design change it is.
 */
export const CALL_KIND = ['summarize', 'visual_plan', 'label', 'summarize_and_plan'] as const;

export type CallKind = (typeof CALL_KIND)[number];

/**
 * Stable failure vocabulary for item-health rows.
 *
 * **Membership is one member per knob an operator turns, not one per gate.**
 * Four HTTP members answer to one fetch, because the fix for a 404 is not the
 * fix for a rate limit. `output_truncated` and `labels_truncated` are the two
 * output budgets, derived from two different grammars, for the same reason.
 */
export const FAILURE_CODE = ['not_attempted', 'robots_denied', 'robots_unreachable', 'blocked_address', 'http_client_error', 'http_rate_limited', 'http_server_error', 'network_error', 'no_text', 'no_title', 'too_short', 'not_prose', 'boilerplate', 'paywalled', 'unsupported_form', 'model_unreachable', 'model_refused', 'model_timed_out', 'context_exceeded', 'output_truncated', 'labels_truncated', 'bad_shape', 'length_out_of_range', 'copied_source', 'leaked_address', 'shard_out_of_time', 'unknown'] as const;

export type FailureCode = (typeof FAILURE_CODE)[number];

/**
 * What the length verdict did with this reply.
 *
 * Recorded because a trimmed summary and a compliant one are indistinguishable
 * afterwards - the ledger stores the length after the trim - so without this
 * field the pipeline cannot say how often the tolerance is doing work.
 */
export const LENGTH_ACTION = ['publish', 'publish_over', 'trim', 'fail'] as const;

export type LengthAction = (typeof LENGTH_ACTION)[number];

export const SUMMARY_STATUS = ['ok', 'failed', 'skipped'] as const;

export type SummaryStatus = (typeof SUMMARY_STATUS)[number];

/** The Summarize stage's output payload, one per item. */
export interface Summary {
	version?: string;

	item_id: string;

	url_key: string;

	/** Our own headline, written from the article's facts. Optional because a title outside the asked range degrades to the source's rather than costing the item (section 1a). */
	title?: string | null;

	summary?: string | null;

	key_points?: string[];

	/** Digest of the words only. Recomputed on read, never trusted. */
	output_digest: string;

	/** The ModelRef id from config. The full ref lives in the manifest. */
	model_id: string;

	/** Which summarize attempt wrote this payload. A count, not a duration - 1 is the first try. It is 1 on every payload and every ledger row ever written: 3,113 of 3,113 rows of state/scores.csv on 2026-08-30. summarize() takes it as a keyword defaulting to 1 and no caller passes anything else, because no retry budget exists yet. Nothing reads it today. It is kept for the retry budget it is named for, so read it as a constant that is reserved and never as a measurement of how often a summary is redone. */
	attempt?: number;

	source_truncated?: boolean;

	/** What the length verdict did with this reply, or null on a payload written before the verdict existed and on any item that never reached it. `publish` is inside the band's ask or inside the tolerance around it; `publish_over` ran long on a band that would rather be long than cut a qualification off the end; `trim` was cut at the last complete sentence that fits; `fail` did not reach the absolute floor and is a failed extraction rather than a summary. */
	length_action?: LengthAction | null;

	/** Prompt tokens, added over every call recorded below. */
	input_tokens?: number;

	/** Tokens written, added over every call recorded below. */
	output_tokens?: number;

	/** Fetch plus extract plus summarize. The three below sum to it. */
	duration_ms?: number;

	/** Network. Says more about the host than us. */
	fetch_ms?: number;

	/** Boilerplate removal and sanitising. */
	extract_ms?: number;

	/** The model, on the stage clock. The only one of the three that a model swap moves, and the one cost below that stays a stage figure: it is the wall clock around every call the stage made, including the HTTP overhead no call reports. */
	summarize_ms?: number;

	/** Reading the prompt, added over every call recorded below. Scales with article length, minus what the cache kept. */
	prefill_ms?: number;

	/** Writing the reply, added over every call recorded below. One token at a time, so about half the prefill rate. */
	decode_ms?: number;

	/** Prompt tokens the runtime reused instead of reading, added over every call recorded below. input_tokens minus this is what prefill_ms actually paid for. Read it per call rather than here when the question is whether the cache answered: a second call that reuses the first call's prompt makes this figure non-zero on every item. */
	cached_tokens?: number;

	/** What the stage's first model call cost, and which call it was. Null on a payload written before 2026-09-12, which recorded a total and no split. */
	call_1?: CallCost | null;

	/** The same for the second call, or null where the stage made only one. */
	call_2?: CallCost | null;

	generated_at: string;

	status: SummaryStatus;

	/** Typed summarize-stage failure, when the cause is already known. Older payloads omit it and still validate. */
	failure_code?: FailureCode | null;

	failure_detail?: string | null;
}
