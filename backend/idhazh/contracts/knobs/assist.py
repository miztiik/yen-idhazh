"""On-device archive search: what the encoder reads, where it comes from, what shows."""

from __future__ import annotations

from pydantic import Field

from idhazh.contracts.base import Model


class AssistConfig(Model):
    """On-device archive search: what the encoder reads, where it comes from, what shows.

    Every value here was a literal with no override path (Guardrail #6). The first two
    describe how much of an item the encoder is allowed to read; the five `model_`
    keys describe where a browser may fetch the encoder and how it proves the bytes
    are ours; the rest describe what the reader's list keeps. All of them are set
    from measurement rather than from taste.

    **Our own origin is primary and the committed weights stay.** The `model_` keys
    are a failover, reached only when this site cannot serve a reader the weights it
    committed. A second origin without `model_digests` would be a permission rather
    than a fallback, so the manifest is the load-bearing half and the URL is the
    convenience.
    """

    max_tokens: int = Field(
        default=256,
        ge=16,
        le=512,
        description=(
            "How far into an item's text the encoder reads before it truncates. 512 "
            "is the hard ceiling because that is the encoder's position table; the "
            "default is 256 because that is what the model was trained at, and "
            "almost no published item runs past it. Raising it would read a little "
            "more text and re-date every committed vector."
        ),
    )
    min_readable_letter_share: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "How much of an item's alphabet the encoder has to know before the item "
            "gets a vector at all. The committed weights carry an English uncased "
            "vocabulary, so an item written in another script still produces a "
            "confident unit vector that no query can retrieve. Below this share the "
            "item gets no vector and the run records why. Half is a plain reading of "
            "'mostly not in our alphabet', and it sits in the middle of an empty "
            "band: a published item either scores near zero or near one, so every "
            "threshold between them selects the same items."
        ),
    )
    model_base_url: str = Field(
        default="https://huggingface.co/Xenova/all-MiniLM-L6-v2",
        pattern=r"^https://[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?(?:/[A-Za-z0-9._-]+)*$",
        description=(
            "The SECOND origin a browser may fetch the encoder from, and only after "
            "our own copy has failed that reader. Our origin stays primary: the "
            "weights are committed under frontend/static/assist/models/ and every "
            "reader gets them from us. This is the failover, and it is a repository "
            "prefix rather than a bare host so the fetch is built from one value - "
            "the path in it is a directory on that host, not a permission, and "
            "frontend/asset-base.js takes only the ORIGIN into connect-src. A GitHub "
            "Release asset cannot serve this: it "
            "carries no Access-Control-Allow-Origin on any hop, so a browser refuses "
            "the fetch. Nothing here reaches the encoder as text (Guardrail #11), "
            "and no payload field, model output or fetched string builds this URL."
        ),
    )
    model_cdn_origins: tuple[str, ...] = Field(
        default=("https://us.aws.cdn.hf.co",),
        description=(
            "The origins model_base_url redirects a large file to, listed because a "
            "browser checks the redirect target against connect-src and would "
            "otherwise refuse it. The small files answer on the base host; the "
            "quantized model redirects to this CDN. "
            "Listing the base host alone passes the four small files and blocks the "
            "weights, which is the worst of both - the reader waits, and "
            "then gets nothing. Kept a separate knob from model_base_url because it "
            "is the other party's delivery network rather than our fetch address, "
            "and it moves when they move it."
        ),
    )
    model_revision: str = Field(
        default="751bff37182d3f1213fa05d7196b954e230abad9",
        pattern=r"^[0-9a-f]{40}$",
        description=(
            "The upstream commit the committed weights are the bytes of, as a full "
            "40-hex SHA-1. A branch name is refused by the pattern, because a branch "
            "hands back whatever was uploaded last and a fetch built on one describes "
            "bytes nobody can fetch again (Guardrail #10). The file tree at this commit "
            "returns a git blob SHA-1 for each small file "
            "and an LFS SHA-256 for the model, all five equal to model_digests below, "
            "and every response at this revision returns it as X-Repo-Commit. It does "
            "NOT identify one commit - the parent carries the same five files - so it "
            "is the head of main on the fetch date rather than something derived from "
            "the bytes. ENCODER_VERSION in frontend/src/lib/assist/encoder.ts is the "
            "browser's copy and backend/tests/test_embed.py fails when the two differ."
        ),
    )
    model_digests: dict[str, str] = Field(
        default_factory=lambda: {
            "config.json": (
                "7135149f7cffa1a573466c6e4d8423ed73b62fd2332c575bf738a0d033f70df7"
            ),
            "onnx/model_quantized.onnx": (
                "afdb6f1a0e45b715d0bb9b11772f032c399babd23bfc31fed1c170afc848bdb1"
            ),
            "special_tokens_map.json": (
                "b6d346be366a7d1d48332dbc9fdf3bf8960b5d879522b7799ddba59e76237ee3"
            ),
            "tokenizer.json": (
                "da0e79933b9ed51798a3ae27893d3c5fa4a201126cef75586296df9b4d2c62a0"
            ),
            "tokenizer_config.json": (
                "9261e7d79b44c8195c1cada2b453e55b00aeb81e907a6664974b4d7776172ab3"
            ),
        },
        description=(
            "SHA-256 of every encoder file, keyed by its path under the model "
            "directory. This is what makes reaching a second origin safe at all: the "
            "browser hashes what arrived and discards the WHOLE set on any miss - a "
            "non-200, a truncation, a timeout or a wrong digest - so provenance is "
            "never mixed across files. Without it, model_base_url would be a "
            "permission for a second party to put bytes into a reader's tab. "
            "Re-derived from the committed files and equal to what the "
            "upstream tree reports at model_revision; "
            "backend/tests/test_embed.py hashes the committed files against this map, "
            "so a manifest that drifts from the weights fails the build rather than "
            "failing closed on every reader."
        ),
    )
    model_fetch_deadline_ms: int = Field(
        default=120_000,
        ge=1_000,
        le=600_000,
        description=(
            "How long the whole second-origin fetch may take before the browser gives "
            "up and tells the reader the download did not finish. It covers all five "
            "files together rather than each one, because a reader is waiting on the "
            "set and a per-file deadline lets four slow files add up to a wait nobody "
            "bounded. Two minutes is the download this failover exists to complete: "
            "the hub serves the quantized model uncompressed where our origin gzips "
            "it, which is seconds on a fast line and minutes on a slow one. A reader "
            "on less than that is better served by the sentence than by a spinner."
        ),
    )
    similarity_floor: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        description=(
            "Cosine similarity a result must reach to be shown at all. A SELECTOR, "
            "never reported to a reader as a quality signal. It sits above where "
            "same-domain noise lands and below where right answers do, so it keeps "
            "almost every right answer and drops almost all of the noise. The noise "
            "distribution did not move when the corpus grew several times over, so "
            "the floor does not move with the archive either. Raising it cuts noise "
            "further and costs measurable recall; the readings are in "
            "docs/concepts/evaluation.md."
        ),
    )
    result_limit: int = Field(
        default=10,
        ge=1,
        description=(
            "How many results the flat list shows. The list carries no rank cue, so "
            "this is also the denominator the recall bar is measured against - the "
            "denominator is min(right answers, this), because more right answers than "
            "slots cannot all be shown."
        ),
    )
    search_months: int = Field(
        default=1,
        ge=1,
        le=12,
        description=(
            "How many month shards a search always reads, newest first. The reader "
            "waits on the download, not on the arithmetic: the fetch is an order of "
            "magnitude more than the ranking at every scope, so this "
            "knob buys download seconds and never compute seconds. One month is the "
            "only scope whose first search "
            "starts inside about five seconds. This is a floor rather than a ceiling: "
            "assist.search_min_days can add one more shard when the newest one is "
            "thin. The page names the days it read, so a wider scope is a sentence a "
            "reader can see."
        ),
    )
    search_min_days: int = Field(
        default=7,
        ge=1,
        le=366,
        description=(
            "The fewest days of published stories a search tries to reach. The scope "
            "is month shards, and a calendar month is not a window: on the last day "
            "of a month the newest shard holds 31 days, and on the next morning it "
            "holds one. That is 31 times less reach for a reason no reader can see, "
            "and a search that finds nothing then looks exactly like a story that was "
            "never published. When the shards search_months names cover fewer days "
            "than this, a search reads ONE more shard - one more and no more, so the "
            "cost is bounded at a single extra fetch. Seven is this knob's own "
            "number rather than one borrowed from a neighbouring window. The extra "
            "fetch fires only in the first days of a month, and only when the shard a "
            "search already reads is small, so the two shards together early in a "
            "month move about what the one shard at the end of a month already moves. "
            "The bytes are levelled across the month rather than doubled."
        ),
    )
    recall_min: float = Field(
        default=0.68,
        ge=0.0,
        le=1.0,
        description=(
            "The regression bar for recall@result_limit over the committed query set, "
            "counted over right answers that carry a vector, scored against the corpus "
            "pinned by eval_corpus_through. Coverage is excluded on purpose: an item "
            "the pipeline never embedded cannot be retrieved at any threshold, so "
            "counting it here would fail this gate for a defect in another stage. Set "
            "two standard errors below the pinned baseline, so ordinary sampling noise "
            "does not fail it. "
            "THIS BAR HAS NO EXPIRY DATE, and that is the whole point of the "
            "pin: a bar scored against a growing corpus expires on its own, whatever "
            "value it is given. Both inputs are fixed, so the number moves "
            "only when the ranking moves or the labels are completed - and completing "
            "the labels raises it rather than eroding it. It is still a LOWER BOUND: "
            "most filled slots hold an item no labeller judged either way, "
            "and every one of them is counted as a wrong answer. `config/idhazh.json` "
            "owns the value. This is a pipeline gate rather than a drawn surface: the "
            "one reader is `backend/tests/test_retrieval_eval.py`, and the frontend's "
            "own `AssistConfig` does not declare the field at all. See "
            "docs/concepts/evaluation.md."
        ),
    )
    eval_corpus_through: str | None = Field(
        default="2026-08-26",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description=(
            "The last published day the retrieval gate scores against, as YYYY-MM-DD. "
            "Set to the day the label set was pooled, so the gate's competitor set is "
            "the one the labellers saw. THIS IS THE FIX FOR A GATE THAT EXPIRES. "
            "Scored against the live archive, recall@10 measures two things at once: "
            "the ranking, and how many stories were published since the labels were "
            "written. Only the first is something a merge candidate can change. The "
            "second is unbounded and monotone - the result list holds a fixed number "
            "of slots and every new item that outranks a gold item evicts it - so the "
            "numerator erodes while the "
            "denominator, min(gold_with_vector, slots), does not move at all. A few "
            "publishing days are then enough to move the instrument as far as the "
            "effect the gate exists to catch, with no code change at all. Pinned, the "
            "drift term is zero "
            "and recall_min measures ranking. Null reads the whole archive, which is "
            "what the printed diagnostic beside the gate reports, because that number "
            "is what a reader actually gets. The reasoning is in "
            "docs/concepts/evaluation.md."
        ),
    )
