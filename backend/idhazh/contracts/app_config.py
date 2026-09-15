"""`config/idhazh.json` - the one tree every block hangs from, and the rules that cross two of them.

One block's knobs live in `idhazh.contracts.knobs.<block>`. This file holds the
aggregate and the five validators no single block can run, because each of them
reads two.

A knob is something a reasonable operator might want set differently without
changing a fact. The runner's own ceilings - 4 vCPU, the 6 h job cap, the 10 GB
cache - are deliberately absent: they are properties of the platform, and making
them editable would invite raising the budget instead of simplifying the feature
(Guardrail #2).

The 1 GB published site is the one that is here, and it is here bounded rather
than trusted. `retention.pages_hard_cap_mb` may name a smaller cap and is
refused above `PAGES_HARD_CAP_MB`, so a config edit can only ever make the site
gate stricter. That is the same rule the absent ceilings obey, held by the schema
instead of by nobody editing a constant.

Every knob ships a sane default, so a fresh clone runs unconfigured.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, ClassVar, Final, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import ChangelogEntry, Contract
from idhazh.contracts.knobs.assist import AssistConfig
from idhazh.contracts.knobs.collect import CollectConfig
from idhazh.contracts.knobs.console import ConsoleConfig
from idhazh.contracts.knobs.evaluation import DriftConfig, EvaluationConfig
from idhazh.contracts.knobs.extract import ElementsConfig, ExtractConfig
from idhazh.contracts.knobs.finetune import FinetuneConfig, ReferenceDatasetConfig
from idhazh.contracts.knobs.models import SUPERSEDED_MODELS_NAMES, ModelsConfig, ModelsFile
from idhazh.contracts.knobs.observability import LoggingConfig, ObservabilityConfig
from idhazh.contracts.knobs.page_weight import PageWeightConfig
from idhazh.contracts.knobs.placement import AssembleConfig, LensWeightsConfig, PlacementConfig
from idhazh.contracts.knobs.removed import refuse_a_removed_knob
from idhazh.contracts.knobs.retention import RetentionConfig
from idhazh.contracts.knobs.run import RunConfig
from idhazh.contracts.knobs.summarize import SummarizeConfig
from idhazh.contracts.knobs.ui import UiConfig
from idhazh.contracts.knobs.visuals import VisualsConfig
from idhazh.contracts.knobs.windows import months_a_window_can_touch

#: The top-level `config/idhazh.json` keys this file used to carry. `models`
#: held the whole active model inline, so a swap edited eleven lines in the file
#: every other knob lives in. It is a file of its own now and `models_file`
#: names which one, so the old block is refused by name rather than lifted: a
#: lift would read one model out of the shared file while `models_file` named
#: another, and the run would stand a server up on whichever won.
SUPERSEDED_APP_NAMES: Final[Mapping[str, str]] = MappingProxyType({"models": "models_file"})


def refuse_an_archive_window_no_preset_offers(ui: UiConfig, console: ConsoleConfig) -> None:
    """The archive's opening span has to be one the shared preset list names.

    Checked here rather than on `UiConfig`, because the presets are
    `ConsoleConfig`'s and the two blocks cannot see each other. Both config
    documents call it, because both carry both blocks.

    This IS the reuse: the archive declares one span and no list of its own, so
    the only list of day counts in the contract is the console's. Let the two
    drift and the archive opens on a window neither control can name, which is
    the failure `console.default_window_days` is already checked against.
    """
    if ui.archive_window_days not in console.window_presets:
        raise ValueError("ui.archive_window_days must be one of console.window_presets")


class AppConfig(Contract):
    """`config/idhazh.json` - every tunable, schema-validated."""

    __schema_stem__: ClassVar[str] = "app-config"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-15T20:00",
            change="The embedded failure vocabulary gained model_refused.",
            why="It follows item-health-row, where the vocabulary is declared.",
        ),
        ChangelogEntry(
            version="2026-09-15T09:00",
            change=(
                "Prose only. No field was added, removed or retyped and no default "
                "moved, so every config/idhazh.json that validated before this still "
                "validates and no read-side migration is owed. What changed is the "
                "`description` text on six blocks, which pydantic lifts from the class "
                "docstring and the Field description into the generated schema: "
                "page_weight, observability, summarize, turns, models and assist drop "
                "the dated incidents, the inline readings and the decision provenance "
                "they were carrying. The rule each one states is unchanged."
            ),
            why=(
                "Guardrail #10 says a rule carries its reason, never its evidence - the "
                "reason is a clause that stays true, the evidence is a reading and "
                "lives in the instrument log. These descriptions are published in "
                "schemas/app-config.schema.json, so a measurement inlined here is a "
                "second copy of one docs/reference/ already holds (Guardrail #4), and "
                "it is the copy nobody re-takes when the subject changes. An operator "
                "reading a knob wants the rule, not the post-mortem of the run that "
                "produced it."
            ),
        ),
        ChangelogEntry(
            version="2026-09-15",
            change="The failure vocabulary this config names gained no_title.",
            why=(
                "Extract gained a refusal for an item whose feed carried no headline. No "
                "knob changed; the vocabulary is inlined into this schema, so the "
                "generated file's bytes move and the change is stamped here rather than "
                "left to the drift gate to announce (section 11). Additive: a config "
                "written before today names none of the new values and still validates."
            ),
        ),
        ChangelogEntry(
            version="2026-09-14T14:00",
            change=(
                "summarize gains asks_for_a_visual_plan, default true. It is the value "
                "the two-call sequence sizes its window with, which classify/dag.py "
                "wrote out as a literal. Additive and defaulted, so a config file "
                "written before today validates unchanged and no read-side migration "
                "is owed. Production is untouched: the default is the literal it "
                "replaced."
            ),
            why=(
                "The pipeline test workflow runs one case with no picture reachable, to "
                "price what the visual decision costs. Turning the picture off is a "
                "config edit already - an empty visuals.enabled_kinds - but the window "
                "sizing had no way to follow it, so that case would reserve room for a "
                "decode it never makes and refuse articles that fit. One knob, so the "
                "two cannot disagree (plan 27, row 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-09-14T13:00",
            change=(
                "logging gains five flags beside level: item_lines, stage_lines, "
                "waiting_heartbeat_seconds, capture_prompts and capture_replies. Each "
                "defaults on, waiting_heartbeat_seconds to 30 seconds and the four "
                "booleans to true, and a negative heartbeat is refused. Additive and "
                "defaulted, so a config file written before today validates unchanged "
                "and a config file with no logging block at all still loads - no "
                "read-side migration is owed. level is untouched at INFO and is "
                "unrelated: these flags decide which records exist, level decides how "
                "loud the logger that prints them is."
            ),
            why=(
                "A 5x model-time regression ran for six days and nothing named it. "
                "Median model time per item moved 97,879 ms to 475,890 ms between run "
                "34745383977 on 2026-09-13 and run 34852763827 on 2026-09-14, and "
                "nothing printed during a 200-minute shard. The new records close that "
                "blind window, and they cost bytes, so each one has to be switchable "
                "on its own - one verbosity dial cannot keep the per-item lines while "
                "dropping prompt capture, which is the expensive one. Every flag "
                "except item_lines carries the reading that retires it on the line "
                "that declares it (Guardrail #6); item_lines carries none because it "
                "is the permanent instrument rather than a debugging aid. This entry "
                "adds configuration only - no record is emitted here. Ruled by the "
                "owner and Fowler, 2026-09-14 (plan 27, row 4)."
            ),
        ),
        ChangelogEntry(
            version="2026-09-14T12:40",
            change=(
                "Added assemble.group_identical_titles, default true. The same-story "
                "pass gains a second way into a group: two items whose published "
                "headlines say the same thing are one story, beside the cosine it "
                "already used. The words must match exactly and the numbers to the "
                "coarser of the two precisions written. Additive with a default, so an "
                "older config/idhazh.json still validates and no read-side migration "
                "is owed. assemble.duplicate_similarity_min is untouched at 0.94."
            ),
            why=(
                "The digest published one story five times in a day and the pass did "
                "not group it. The vector is built from `title. summary`, the summary "
                "is our own prose about ONE article and is most of the string, so two "
                "outlets on one story never converge. Measured 2026-09-14 over the "
                "twenty-five committed days: the fifty-three cross-source pairs that "
                "share a headline have a median cosine of 0.9177, and the pair a person "
                "marked as two stories sits at 0.9317 - the populations overlap, so the "
                "threshold was never the defect. The knob exists because the new joiner "
                "has no threshold of its own, so without it part of the pass would be "
                "invisible to config/ (Guardrail #6). Ruled by Andre, the Editor and "
                "Fowler, 2026-09-14; the rounding tolerance on numbers by the owner the "
                "same day, measured to admit twelve cross-source pairs over those days "
                "and no false merge."
            ),
        ),
        ChangelogEntry(
            version="2026-09-14T11:00",
            change=(
                "lens_weights is new, with three knobs: counterfactual_multiplier, "
                "counterfactual_refused_per_desk and window_days. Additive and "
                "optional - the block carries a default for every knob, so a config "
                "file written before today validates unchanged and a fresh clone runs "
                "on the defaults."
            ),
            why=(
                "Every run now scores a bounded pool of its candidates a second time at "
                "a candidate lens weight and writes both scores to "
                "state/counterfactual-scores/. Nothing moves as a result. The block "
                "holds what the run asks - the multiplier - and what it costs - how "
                "many refused candidates a desk records, and how long the rows are "
                "kept."
            ),
        ),
        ChangelogEntry(
            version="2026-09-14T09:30",
            change=(
                "visuals.canvas_width is gone and nothing replaces it, and so is the "
                "VisualsConfig.canvas_height property derived from it. This is a "
                "contract break and the read-side migration ships with it: a config "
                "that still carries the knob is refused by name through "
                "refuse_a_removed_knob rather than through 'extra inputs are not "
                "permitted'. Refused rather than lifted, because there is no knob left "
                "that answers the same question - a width the operator sets and a width "
                "the reader's screen has are not the same number, and carrying the old "
                "one forward would let somebody keep believing they had set the drawing "
                "box."
            ),
            why=(
                "Plan 12 row #2. The knob sized one fixed drawing box for every visual, "
                "back when the pipeline rendered the picture. The reader's browser draws "
                "it now (owner ruling, 2026-09-13) and takes the width the card actually "
                "gives it, measured in the browser - so no build-time number can say how "
                "wide a drawing is, and one that tried would only ever be a scale factor "
                "shrinking the drawn type. The smallest drawn string read 4.8 CSS px at "
                "a 390 px viewport against a --text-xs of 12, which is 60 percent under "
                "the token it was set from, and that scale is what this removal ends. "
                "canvas_height went with it because it was 16:10 of a number that no "
                "longer exists and had no caller of its own."
            ),
        ),
        ChangelogEntry(
            version="2026-09-14T05:00",
            change=(
                "config/idhazh.json moves extract.truncation_cap_tokens from 10000 to "
                "20000, models.summarize.inference.n_ctx from 49152 to 65536 and "
                "finetune.sequence_length from 16384 to 32768. No field was added, "
                "removed or retyped. InferenceConfig.n_ctx and "
                "FinetuneConfig.sequence_length restate their arithmetic against the "
                "new cap; neither default moves, so a fresh clone still runs the "
                "conservative pair."
            ),
            why=(
                "Plan 28 row #13b. The three tokenizer readings every one of these "
                "sums is spent at were taken against the retired 8B. Retaken against "
                "the configured weights, tokens a word at the cut went 1.3 to 1.3628, "
                "so the cap and both windows were being derived at the wrong rate for "
                "the vocabulary that reads them. At the new cap the two calls size at "
                "54,887 tokens of 65,536 and a training row at 25,156 of 32,768, both "
                "asserted in backend/tests/contracts/test_app_config.py against config "
                "rather than against a pinned number. Memory is what a window costs "
                "and 65536 costs 1,584 MiB more than 16384, against a 6.84 GiB "
                "low-water free the runner measured - docs/reference/benchmarks/"
                "two-call-window-sizing.md."
            ),
        ),
        ChangelogEntry(
            version="2026-09-14T04:00",
            change=(
                "run.shard_size and run.shard_timeout_minutes carry the derivation "
                "that produced them rather than the one they were set under. Neither "
                "number moves: the derived worst shard is 96.1 minutes against a "
                "200-minute bound, and shard_size would have to rise above 20 to move "
                "the fan-out at all."
            ),
            why=(
                "Plan 28 row #10. A call is decoded as two spans now, so the worst-case "
                "item is not the one either number was sized against and carrying them "
                "forward would leave two backstops nobody could re-derive. Ruled by "
                "Carmack, 2026-09-14."
            ),
        ),
        ChangelogEntry(
            version="2026-09-14",
            change=(
                "models is gone and models_file replaces it. The block held the whole "
                "active model inline; the same shape is now the models-config document "
                "under config/models/, and models_file names which of those files is "
                "read. This is a contract break and the read-side migration ships with "
                "it: a config that still carries models is refused by name through "
                "refuse_a_removed_knob rather than through 'extra inputs are not "
                "permitted'. Refused rather than lifted, because a lift would read one "
                "model out of the old block while models_file named another file, and "
                "the run would stand a server up on whichever won. models_file defaults "
                "to the committed file, so a fresh clone still runs unconfigured, and "
                "its grammar pins it to config/models/ and to .json - the value is an "
                "operator's edit that becomes a path this build opens."
            ),
            why=(
                "Plan 28 row #6. Swapping the summarizer had to cost no source edit and "
                "did not: it cost eleven lines edited in place in the file every other "
                "knob lives in, and a revert had to reconstruct the previous model's "
                "measured numbers out of git rather than read them off disk. One file "
                "per model makes the swap and the revert the same one-line edit, and "
                "puts the numbers measured for a set of weights in the file that names "
                "them. Ruled by Fowler, 2026-09-14."
            ),
        ),
        ChangelogEntry(
            version="2026-09-13T23:55",
            change=(
                "models.<role>.turns is new, required, and has no default. It carries "
                "turn_opening, turn_closing, reply_opening, reply_opening_thinking and "
                "declared_for, which must name the same weights the entry does - the "
                "rule models.<role>.inference.declared_for already obeyed, now checked "
                "for both blocks in one loop. turn_opening must name $role and the "
                "other three may not be empty. The four strings come verbatim from "
                "backend/idhazh/prompts/turn_markers.json, which is deleted in this "
                "commit; config load refuses that path if it comes back, because an "
                "operator editing a file nothing reads is the failure the package "
                "location was supposed to prevent. There is no read-side alias for the "
                "old location: a config file is a file a person edits, and silent "
                "acceptance teaches the wrong place to put it. The field sits on a new "
                "ModelEntry, which is ModelRef plus the envelope, so the shape a run "
                "records is unchanged."
            ),
            why=(
                "Plan 28 row #2. The turn envelope is a fact about somebody else's "
                "weights, and it was held in a package this project writes, apart from "
                "the entry naming those weights. A swap moved the entry and left the "
                "markers, and nothing raised - a wrong marker renders a prompt with no "
                "turn structure that the grammar still accepts, so the only symptom is "
                "worse summaries. On the entry, a model whose turns differ is a config "
                "edit rather than a source edit, and declared_for makes the swap that "
                "forgets them loud. It is required on the declared shape only, because "
                "run_manifest.ModelUse embeds ModelRef and no model_ref a run has ever "
                "written carries markers - requiring it there would stop this build "
                "reading them. So run.json never records the envelope, and what still "
                "catches a moved marker is RunRecord.inputs.prompt_sha256, which "
                "digests both turns rendered through it. Ruled by Fowler, 2026-09-13."
            ),
        ),
        ChangelogEntry(
            version="2026-09-13T23:50",
            change=(
                "observability.visuals_full_grain_months added, defaulting to 14, and "
                "observability.visual_aggregate_keep_months added, defaulting to null. "
                "The second must sit above the first, which the existing pair validator "
                "now checks for all three folded stores."
            ),
            why=(
                "state/visuals/ takes the fold policy, and a fold needs an age or it "
                "never happens. It is a named per-store window rather than a share of "
                "anybody else's, because the visual ledger answers a different question "
                "from the item-health census and from the eval ledger, and one number "
                "standing for three stores is the knob this project already removed "
                "once. Fourteen matches the two it is read beside. The pair rule is the "
                "same rule the other two aggregates carry: a summary set to expire "
                "before the rows it replaces would delete a month that was never folded."
            ),
        ),
        ChangelogEntry(
            version="2026-09-13T23:30",
            change=(
                "Four keys are gone in one commit: models.visual_planner, "
                "run.two_calls_per_item, run.visual_planner_budget_minutes and "
                "finetune.student. This is a contract break and the read-side migration "
                "ships with it - each name is refused by name through "
                "refuse_a_removed_knob rather than through 'extra inputs are not "
                "permitted', and so are the two older spellings that used to migrate "
                "into them, models.route and run.route_budget_minutes. A removed knob "
                "now carries an empty replacement, which the refusal reads as 'gone and "
                "nothing replaces it' - the rename maps RENAMED_MODELS_KEYS and "
                "RENAMED_RUN_KEYS retired with the keys they pointed at, because a "
                "rename onto a deleted key is a migration that silently loses a number. "
                "finetune.teacher keeps its default of summarize and is the only role "
                "left; a teacher still naming visual_planner or route is answered by "
                "name rather than by a list of legal keys."
            ),
            why=(
                "Plan 11 row #6. The work stage makes two calls per item on the "
                "summarizer weights - the label call labels, the summarize-and-plan call writes "
                "the summary and then the picture - so the small visual planner decides nothing, "
                "and a model nothing calls is a download, a cache entry and a 50-minute job the "
                "run waits on. Owner ruling 2026-09-13: move forward, no rollback, so the "
                "flag goes away with the model rather than staying as a second "
                "implementation (Guardrail #6). finetune.student had no reader and named "
                "the retired model; re-pointing it at summarize would make the teacher "
                "and the student one model, which is a session that trains a model on "
                "its own output."
            ),
        ),
        ChangelogEntry(
            version="2026-09-13T23:00",
            change=(
                "ui.pill_move_min added, defaulting to 2 and bounded 1 to 3, and "
                "ui.topic_pills_max's default moves from 8 to 5 with its description "
                "rewritten. The shape is `UiConfig`, which this document and "
                "`AppearanceConfig` share, so both schemas moved together. The new key "
                "is additive with a default, so a config written before today still "
                "validates. The moved default is NOT a contract break either - every "
                "committed config names the key - but a checkout with no config file "
                "now draws five pills where it drew eight."
            ),
            why=(
                "The topic row now orders by how much of the day each desk holds, and "
                "an order refreshed five times a day needs a margin or a one-story "
                "lead moves a control the reader is pointing at. Eight was a cap "
                "nothing could reach: config/taxonomy.json declares five verticals, so "
                "the row never folded and the number said nothing about the row. "
                "Measured 2026-09-13 over the 23 committed days carrying all five "
                "desks, 92 adjacent pairs: a margin of two shows a smaller count ahead "
                "of a bigger one on one pair in 92, reading 1 ahead of 2. The same "
                "measurement found the margin does not steady the row across days - 31 "
                "desk-days move at two against 28 at one - so it bounds the reason a "
                "desk moves and not how often. Ruled by Editor, 2026-09-13; the row is "
                "plan 25 row #6."
            ),
        ),
        ChangelogEntry(
            version="2026-09-13T22:00",
            change=(
                "collect.repetition_weight removed and collect.carriage_step added at "
                "0.25. Carriage stops multiplying a story's authority and becomes one "
                "flat step that fires at two carriers and never grows. "
                "ui.lead_shared_subject_weight's bound moves with it: it was "
                "collect.tier_weights.trade_press times collect.repetition_weight, and "
                "it is now collect.carriage_step, because the term it bounds no longer "
                "multiplies a tier. This removes a key, so a config/idhazh.json still "
                "carrying repetition_weight is refused on read rather than silently "
                "ignored - the committed file drops it in this commit. No published "
                "payload schema moves: carried_by is written and read exactly as "
                "before, and only what the ranker pays for it has changed."
            ),
            why=(
                "A multiplier pays most to whatever already scored highest, which is "
                "the opposite of what a tie-break does, and it was uncapped - a story "
                "on six feeds took the day. What the number counts is syndication "
                "rather than agreement, which docs/concepts/digest.md already refuses "
                "to print in words while the ranker made the claim in arithmetic. "
                "Measured 2026-09-13 over the 13 committed days that carry rank_score, "
                "5,682 stories: a second feed carries 323 of them - 5.7 percent - and "
                "they held 54 of the 260 framed head slots, 20.8 percent. At a flat "
                "0.25 they hold 20, 7.7 percent, which is the base rate and a bit. The "
                "day's shape does not move - 5 desks, a median 16 feeds in the head, "
                "the biggest desk still a median quarter of it - and 179 of 260 head "
                "slots change occupant, with the lead changing on 8 of 13 days. Every "
                "one of those eight swaps replaces wire copy two or three of our feeds "
                "repeated with a story one feed carried from the organisation it is "
                "about. Ruled by Editor, 2026-09-13; the measurements and the cost to "
                "the reader are in docs/concepts/placement.md."
            ),
        ),
        ChangelogEntry(
            version="2026-09-13T21:00",
            change=(
                "config/idhazh.json moves models.summarize.inference.n_ctx from 16384 "
                "to 49152, and InferenceConfig.n_ctx's description carries the KV "
                "reading behind it. No field was added, removed or retyped, and the "
                "default stays 8192."
            ),
            why=(
                "The two-call path did not fit the old window and does not fit the "
                "32768 an owner authorised on 2026-09-12 either. Measured 2026-09-13 "
                "on the configured weights through llama-server's own tokenizer: at "
                "the 10,000-token truncation cap, the label call's prompt plus its 6,491-token "
                "output budget plus the 58-token seam plus the summarize-and-plan call's "
                "4,694-token budget sizes at 39,284 tokens. Three of eight cap-length articles "
                "built from corpus prose measured over 32,768 on their own, the worst at 37,495. "
                "49152 is that sum plus a 25 percent margin, rounded up to the next "
                "whole multiple of 16384 and of the 512-token batch. The 25 percent is "
                "the size of the one tokenizer miss on record - measured's "
                "WORST_TOKENS_A_WORD says 1.585 tokens a word and the densest "
                "cap-length build delivered 1.952, 23 percent over - so the margin has "
                "a derivation somebody can re-take. It leaves 9,868 spare, which means "
                "the assertion still fails a merge once the sequence grows a quarter. "
                "Memory is what the window costs and it is not what chose this value: "
                "KV runs 32 KiB a token over 8 attention layers of 32, so 49152 is "
                "1,536.00 MiB against 512.00 at 16384 - 1,056 MiB more all told, "
                "against the 6.84 GiB low-water free the runner measured on 2026-09-10 "
                "and a 1.0 GiB bar, which every candidate from 32768 to 65536 clears by "
                "more than four times. The model trains to 262,144, so no RoPE scaling. "
                "Ruled by Carmack, 2026-09-13, over the 65536 this branch first "
                "carried: 65536 fits too and costs 528 MiB more, but it leaves 67 "
                "percent of the window spare, and a window the sequence cannot fill is "
                "a gate nobody hears. Re-derive it when extract.truncation_cap_tokens "
                "is fixed or elements.max_per_article moves."
            ),
        ),
        ChangelogEntry(
            version="2026-09-13T18:00",
            change=(
                "collect.front_page_bonus removed. An aggregator's front-page vote no "
                "longer moves the order, and the four terms the order is now built "
                "from - collect.tier_weights, collect.recency_weight, "
                "collect.reliability_floor and collect.watchlist_bonus - each gained "
                "the measurement behind its size. This removes a key, so a "
                "config/idhazh.json still carrying front_page_bonus "
                "is refused on read rather than silently ignored - the committed file "
                "drops it in this commit, and nothing a run writes carries it, so there "
                "is no payload to migrate."
            ),
            why=(
                "rank_score used to decide only what was admitted; since 2026-09-13 it "
                "also decides the order a reader meets. A term that moves an order has "
                "to fire often enough that a move can be attributed to it. Measured "
                "2026-09-13 over the 13 committed days that carry rank_score, 5,682 "
                "stories: an aggregator front page fired on 8 of them - 0.1 percent, "
                "and 2 of 260 head slots - while being worth 0.4, more than the 0.3 "
                "step between the community and trade-press tiers. Removing it takes no "
                "story out of the first twenty on any of the 13 days, and it does change "
                "which of those twenty leads on 2 of them: a term that is silent 99.9 "
                "percent of the time and then decides the lead is a lottery rather than "
                "a ranking term. "
                "on_front_page is still computed and still "
                "published, so the page can still say another desk led with the story "
                "and a later row can restore the term once the signal is actually "
                "being supplied. Ruled by Editor, 2026-09-13."
            ),
        ),
        ChangelogEntry(
            version="2026-09-13T14:00",
            change=(
                "Added the reference_dataset block - rows_per_split_min 200, "
                "domains_per_split_min 20, rows_per_domain_max 7, article_words_min 120 "
                "and request_delay_seconds 1.0. Additive and defaulted, so a "
                "config/idhazh.json written before this still loads and needs no "
                "read-side migration."
            ),
            why=(
                "corpus/reference-dataset-1/ is the frozen set every classification "
                "accuracy number in plan 23 is measured on, and the floors that keep it "
                "honest are what stop a lopsided split passing a disjointness test. A "
                "floor written as a literal cannot be rebuilt at another size without a "
                "code change (Guardrail #6), and the whole point of these five is that "
                "somebody can raise one and rebuild."
            ),
        ),
        ChangelogEntry(
            version="2026-09-13T12:00",
            change=(
                "Added the placement block - placement.head_items 20, "
                "placement.max_desk_in_head 5 and placement.head_no_repeat 10. "
                "Additive and defaulted, so a config/idhazh.json written before this "
                "still loads and needs no read-side migration; the committed file "
                "sets all three explicitly, which is what makes the frame visible to "
                "an operator reading it."
            ),
            why=(
                "The published day now has one order over the whole day instead of a "
                "desk-blocked one, and these are the two standing editorial decisions "
                "that bound its head: how much of it one desk may hold, and how far "
                "down it one feed may repeat. Nobody reads the digest before it "
                "publishes and it publishes five times a day, so an editor's judgement "
                "can only reach a reader as arithmetic. Measured 2026-09-13 over the "
                "13 committed days carrying rank_score: the biggest desk in the top 20 "
                "ran at a median of 12 and reached all 20 on 2026-09-07, and the "
                "biggest feed in the first ten ran from 3 to 8."
            ),
        ),
        ChangelogEntry(
            version="2026-09-13",
            change=(
                "retention.image_months is re-valued in config/idhazh.json from -1 to "
                "13, and its description carries the derivation. No key was added, "
                "removed or retyped, and the default on the model stays -1 - so a "
                "config written before this still loads and needs no read-side "
                "migration. retention.dry_run stays true, so nothing is deleted by "
                "this."
            ),
            why=(
                "-1 switched the age window off entirely, so this is the first age "
                "window this project has had rather than a tightening of one. The "
                "value was an owner decision with no measurement behind it; the rate "
                "it needed was taken on 2026-09-13 over the 23 dated directories "
                "under frontend/public/digest/. Rendered visuals arrive at 324,580 "
                "bytes a published day over the 19 days past the startup regime, so "
                "390 days stands at 120.7 MiB for ever, 11.8 percent of the 1 GiB "
                "Pages ceiling. 12 and 14 months are 18.6 MiB either side of it "
                "against a one-spread band of 47.6 MiB, so the byte budget cannot "
                "separate them and the owner's 13 stands (Carmack, 2026-09-13)."
            ),
        ),
        ChangelogEntry(
            version="2026-09-12T21:00",
            change=(
                "evaluation.label_min_stratum_rows is REMOVED, and "
                "evaluation.label_min_run_days no longer mentions a pipeline stratum."
            ),
            why=(
                "It bounded how few rows one pipeline stamp could contribute to a draw "
                "before a result read off that stratum was refused. The stamp stopped "
                "being written on 2026-09-12, so a draw is one pool at one scorer and "
                "there is no stratum left to be thin. config/idhazh.json never set the "
                "key, so the committed file is unchanged. BREAKING for a file that sets "
                "it - the read-side migration is that the key is dropped rather than "
                "defaulted, and a config carrying it is refused rather than silently "
                "ignored."
            ),
        ),
        ChangelogEntry(
            version="2026-09-12T12:00",
            change=(
                "Added run.two_calls_per_item, a boolean defaulting to false. Additive "
                "and defaulted, so config/idhazh.json written before this still loads "
                "and needs no read-side migration; the committed file sets it false "
                "explicitly, which is what makes the knob visible to an operator "
                "reading it."
            ),
            why=(
                "Plan 11 rows 1 to 5 built two model calls, the reachability gate, the "
                "downgrade ladder and one renderer, and no stage dispatched any of "
                "them. This is the switch the plan's own strategy named - behind a "
                "flag, off, until the whole path works. Row #6 then deletes the flag, "
                "the small model and the visuals job in one commit."
            ),
        ),
        ChangelogEntry(
            version="2026-09-12",
            change=(
                "ui.rail_group_minutes is REMOVED. The shape is `UiConfig`, which "
                "this document and `AppearanceConfig` share, so both schemas moved "
                "together; the appearance document also drops frame.zone_time_rem, "
                "which only it carried. config/idhazh.json never set the key, so the "
                "committed file is unchanged. BREAKING for a file that sets it - the "
                "read-side migration is that the key is dropped rather than "
                "defaulted, and a config carrying it is refused rather than silently "
                "ignored."
            ),
            why=(
                "The day's time rail is deleted, and this was how coarsely it grouped "
                "stories into markers. Every story now prints its own published time "
                "in its eyebrow, so there is nothing left to group. Re-measured "
                "2026-09-12 over 8,922 committed items in 22 days: at the 60-minute "
                "default the rail drew 1,218 markers, so 86.3 percent of stories "
                "carried no time at all."
            ),
        ),
        ChangelogEntry(
            version="2026-09-10T22:00",
            change=(
                "page_weight.ceilings_bytes loses /archive/, /console/, "
                "/console/machine/ and /console/model/ from config/idhazh.json. /404 "
                "and /evals/ stay. No key was added, removed or retyped on the model - "
                "the object was already free-form and its default was already empty - "
                "so no committed config becomes invalid and no payload needs a "
                "read-side migration."
            ),
            why=(
                "Owner ruling, 2026-09-10: no number comparison. Those four routes grow "
                "when the pipeline publishes, so their numbers had to move when nobody "
                "wrote any code, and the only way past a firing was to type a bigger "
                "one - /archive/ was raised twice in one day on 2026-08-26 and then "
                "removed. The same instrument failed the other way at the same time: "
                "/console/ stood at 7.2 times the page it bounded for four days with "
                "the build green, because a number too loose is as green as a number "
                "too tight. Measured: the ceilings block was edited 22 times in the 16 "
                "days from 2026-08-26, against 11 edits to the whole gate script that "
                "reads it. The one regression this surface has ever had is a layout "
                "inlining a day payload, 313,300 gzipped bytes, which is a yes-or-no "
                "fact rather than a size - and frontend/tests/payload-weight.spec.ts "
                "already asserts it directly, with no number in it, returning the same "
                "verdict whatever the archive holds. /404 and /evals/ stay because they "
                "pass the test the four failed: they move only when a person edits "
                "source."
            ),
        ),
        ChangelogEntry(
            version="2026-09-10T20:00",
            change=(
                "Every page_weight number is a guardrail rather than a budget, and the "
                "six committed route values were raised to twice the heaviest of five "
                "builds: /404 2,400 -> 4,400, /archive/ 6,400 -> 12,000, /console/ "
                "52,000 -> 96,000, /console/machine/ 50,000 -> 92,000, /console/model/ "
                "63,000 -> 116,000, /evals/ 3,600 -> 6,600. No key was added, removed or "
                "retyped, and no committed config becomes invalid. "
                "page_weight.payload_ceilings_bytes and cold_console_load_bytes were "
                "already 2.5 and 6.8 times what they bound, so neither value moved; only "
                "the words describing them did."
            ),
            why=(
                "Owner ruling, 2026-09-10: 'any ceiling is a guideline not a rule - "
                "increase with twice the buffer and document it is a guard rail.' The six "
                "route numbers sat 6 to 14 percent above the pages they bound, which is a "
                "budget: an ordinary content day reaches it, somebody raises the number, "
                "and the gate teaches an operator that raising numbers is what a red gate "
                "asks for. At twice the page only a change of a different order fires it - "
                "a layout inlining a day payload, a panel that stops fetching and starts "
                "embedding - so a fired guardrail is a question about the bytes rather "
                "than about the number. Measured 2026-09-10 at c40eda91, gzip -5, node "
                "24.12.0, five builds of the shipping tree, heaviest of the five with the "
                "spread over them in brackets: /404 2,154 (7), /archive/ 5,761 (8), "
                "/console/ 47,077 (8), /console/machine/ 45,254 (3), /console/model/ "
                "57,488 (5), /evals/ 3,227 (3). Each new value is twice the heaviest, "
                "rounded up to a number a person can read, which lands them 2.02 to 2.08 "
                "times the page."
            ),
        ),
        ChangelogEntry(
            version="2026-09-10T14:00",
            change=(
                "summarize gains key_point_words_max, the first length rail a key "
                "point has ever had. config/idhazh.json does not set it, so the "
                "committed file is unchanged and the value ships as its default of 80 "
                "words. Additive and defaulted, so a config file written before today "
                "still validates; the decoder rail it produces is looser than anything "
                "the pipeline has emitted, so no reply that parsed yesterday stops "
                "parsing."
            ),
            why=(
                "The planner's second call decodes the summary and the visual plan "
                "through one output budget, and that budget is derived from the reply "
                "shape's own bounds rather than picked. Every other field in the shape "
                "carried a maxItems or a maxLength; a key point was a bare string, so "
                "the arithmetic had a term in it with no upper end and the derivation "
                "was not a derivation. The rail is deliberately loose: measured "
                "2026-09-10 over the 32,353 key points in the committed digest days, "
                "the longest is 66 words and 418 characters against a mean of 16.7 "
                "words, and a maxLength is a hard grammar stop, so a tight rail would "
                "convert an occasional long key point into a failed item."
            ),
        ),
        ChangelogEntry(
            version="2026-09-10T12:00",
            change=(
                "PageWeightConfig gains payload_ceilings_bytes and "
                "cold_console_load_bytes, both empty by default so a config written "
                "before today still validates. page_weight.ceilings_bytes is now read "
                "as gzip -5 rather than gzip -9, and all six committed values were "
                "re-measured at that level in the same commit: /404 2,200 -> 2,400, "
                "/archive/ 7,553 -> 6,400, /console/ 335,051 -> 52,000, "
                "/console/machine/ 44,706 -> 50,000, /console/model/ 56,385 -> 63,000, "
                "/evals/ 3,279 -> 3,600. No key was removed and no type changed."
            ),
            why=(
                "Two of these numbers had stopped describing the site. /console/ was "
                "sized when the console inlined its telemetry and the document weighed "
                "3.88 MB; the page is 46,773 gzip -5 bytes now, so the ceiling stood at "
                "7.2 times the page it was meant to bound and could not have caught any "
                "regression short of a sevenfold one. The level moved because -9 is not "
                "what a reader pays: measured 2026-09-10 against the live Pages origin, "
                "it served /console/ in 46,917 bytes where a local gzip -5 makes 46,787 "
                "and a gzip -9 makes 45,077, and /archive/ in 5,760 against 5,755 at -5 "
                "- so -5 is within 0.3 pct of the wire and -9 understates it by 3.9 pct. "
                "The level and the six values had to move together: at -5 the tree "
                "already stood over two of the old ceilings, so either half alone leaves "
                "the build red. The two new keys bound what the document ceilings "
                "stopped being able to see. Moving the console's telemetry out of its "
                "HTML took 3.4 MB off a document that a ceiling watched and put it into "
                "files that nothing watched; payload_ceilings_bytes watches them, and "
                "cold_console_load_bytes bounds how many of them one opening of the page "
                "may want, which is a property of the design rather than of the data."
            ),
        ),
        ChangelogEntry(
            version="2026-09-10T09:00",
            change=(
                "AssistConfig gains five keys: model_base_url, model_cdn_origins, "
                "model_revision, model_digests and model_fetch_deadline_ms. "
                "config/idhazh.json sets none of them, so the committed file is "
                "unchanged and every value ships as its default. The shape is shared "
                "with AppearanceConfig, so appearance-config is restamped with the "
                "same version. Additive and defaulted, so a config file written "
                "before today still validates."
            ),
            why=(
                "The encoder had exactly one origin, and a reader whose fetch of it "
                "failed had no search at all. These five name a second one and, more "
                "to the point, name what makes reaching it safe: the browser hashes "
                "every arriving file against model_digests and discards the whole set "
                "on any miss, so a second party can put no unverified byte into a "
                "reader's tab. Our own origin stays primary and keeps the committed "
                "weights - nobody pays the hub's extra 6.75 MB unless this site has "
                "already failed them. model_cdn_origins is a separate key because a "
                "browser checks a redirect target against connect-src: measured "
                "2026-09-09 from the live Pages origin, 15 reads of 15, the four "
                "small files answer on the base host and the 23 MB of weights answers "
                "302 to a CDN, so listing the base host alone passes the small files "
                "and blocks the model. A GitHub Release asset was measured the same "
                "day and cannot serve this at all - no Access-Control-Allow-Origin on "
                "any hop, 15 refusals in 15 attempts - which is why the second origin "
                "is the hub rather than a copy we publish."
            ),
        ),
        ChangelogEntry(
            version="2026-09-10T00:30",
            change=(
                "evaluation.summary_words_min and evaluation.summary_words_max are "
                "removed. summarize gains length_policy (overshoot_ratio, "
                "overshoot_words, undershoot_ratio, absolute_floor_words, "
                "floor_applies_above_source_words) and each band gains "
                "over_length_action. The ladder drops to five rungs and its ceiling "
                "moves from 230 to 200: 0|30-45, 60|45-80, 700|70-130, 2000|95-160, "
                "4000|120-200. A read-side migration drops the two old keys, and "
                "AppConfig._the_ask_sits_inside_the_gate is gone with them."
            ),
            why=(
                "The two removed integers were one global pair applied to all six rungs "
                "of a ladder they could not see, and a reply outside them returned "
                "LENGTH_OUT_OF_RANGE, which deletes the item from that day's digest with "
                "no second attempt. So a 251-word reply to a 230-word ask lost the story "
                "outright, and the same pair capped how much any rung could ever ask "
                "for. Length is the one property a reader can judge unaided - a summary "
                "that is too long is a summary they stop reading, and a summary that is "
                "missing is nothing at all - so it may not be the property that silently "
                "removes a story. The tolerance is now derived from the band the item "
                "landed in, and the only length that still fails an item is "
                "absolute_floor_words, which catches a failed extraction rather than a "
                "long reply. The ladder is editorial rather than measured: an "
                "informative abstract is capped near 250 words whether the source is "
                "4,000 words or 40,000 (ANSI/NISO Z39.14), so the ask grows with the "
                "source logarithmically and then stops. 200 is the ceiling because two "
                "minutes of adult non-fiction reading is about 480 words, thirty titles "
                "spend 250 to 300 of them, and a 200-word item is already 50 seconds on "
                "one story out of thirty. The rungs at 3000 and 5000 collapse into one "
                "at 4000 because the model is handed at most 7,692 words, so every "
                "source past 4,000 arrives with much the same evidence. None of these "
                "numbers came from state/scores/: the prompt is being tuned and a "
                "fine-tune is in flight, so our own length figures describe a pipeline "
                "mid-repair (Guardrail #10)."
            ),
        ),
        ChangelogEntry(
            version="2026-09-09T23:45",
            change=(
                "finetune.sequence_length default and config/idhazh.json both move from "
                "8192 to 16384, which is models.summarize.inference.n_ctx. No field was "
                "added, removed or retyped."
            ),
            why=(
                "The other half of the cap raise earlier the same day, which the entry "
                "below deferred. The cap went to 10,000 tokens and the window to 16,384, "
                "so the longest article the pipeline now reads makes a 14,088-token "
                "sequence - 997 of prompt overhead, 12,191 of article, 900 of answer, "
                "measured over the 4,117 published items in state/item-health/2026-09.csv "
                "(2026-09-01 to 09, stock ubuntu-latest 4 vCPU runners). At 8,192 the "
                "wrangler and the notebook DROPPED that row and counted it, so the "
                "training set quietly lost every article past about 5,500 words while "
                "production kept summarizing them: the model would have been tuned on "
                "the short half of the work it does. Dropping is the right refusal - a "
                "truncated target teaches the model to stop mid-summary - so the fix is "
                "to stop making rows that have to be refused. 16384 is n_ctx rather than "
                "a second derivation, because a training row is a prompt the pipeline "
                "could have sent and an answer it could have returned; one number now "
                "covers both, and test_the_training_window_covers_the_longest_row_the_cap_"
                "allows fails on any later pair that does not fit. The cost is GPU memory "
                "on the machine that trains, quadratically in attention. That machine is "
                "not the runner, so Guardrail #2's budget does not price it, and no number "
                "here is a measurement of a card - nothing has trained yet (Guardrail #10). "
                "The escape hatch is per-session and already existed: "
                "SEQUENCE_LENGTH_OVERRIDE in notebooks/finetune.ipynb lowers it for a "
                "card that cannot hold the row, and prints how many rows that dropped."
            ),
        ),
        ChangelogEntry(
            version="2026-09-09T23:30",
            change=(
                "ConsoleConfig gains shimmer_after_ms, defaulting to 400 and bounded "
                "at 0 and 5000. config/appearance.json sets it to 400. The shape is "
                "shared with AppearanceConfig, so appearance-config is restamped with "
                "the same version. Additive and defaulted, so a config file written "
                "before today still validates."
            ),
            why=(
                "The console started fetching its months on 2026-09-09, so for the "
                "first time a panel on this site has a wait to draw. A reserved block "
                "that animates the moment it appears turns a 90 ms fetch into a "
                "flicker, so the shimmer waits and a fetch that lands first never "
                "animates at all. It is a knob rather than a literal because the right "
                "value is a property of the payloads and the network, not of the "
                "stylesheet (Guardrail #6). FOUR HUNDRED IS A DECLARED ESTIMATE, not a "
                "measurement: no median payload arrival has been taken since the "
                "fetches landed, and Guardrail #10 refuses an unmeasured number the right "
                "to justify a design, so this one justifies nothing - it is the value "
                "the surface ships on until somebody re-derives it from the measured "
                "median a payload takes to reach a reader. The shell-and-fetch "
                "migration was meant to and could not: that number is a reader-facing "
                "timing measurement, which the same plan scoped out (owner, "
                "2026-09-08). docs/reference/measurements.md carries what would settle "
                "it. Ruled by Fowler, 2026-09-08: a user-interface row is not a "
                "measurement harness."
            ),
        ),
        ChangelogEntry(
            version="2026-09-09T23:00",
            change=(
                "summarize.bands gained a sixth rung at min_source_words 5000, asking "
                "180 to 230 words and the same 2 to 5 key points as the rung below it. "
                "No existing rung moved and evaluation.summary_words_max did not move."
            ),
            why=(
                "extract.truncation_cap_tokens went to 10000 earlier the same day, so "
                "the model is now handed 7,692 words rather than 3,846 and the top rung "
                "covers a span twice as wide as the one it was cut for: a 3,000-word "
                "piece and a 7,692-word piece both arrive whole and both got the "
                "identical 150-to-230-word ask, at 20 to 1 and 51 to 1. The floor is "
                "5000 because 5,346 is the midpoint of that whole-read range and 5000 is "
                "the nearest seam the ledger reports, which is how the fifth rung's "
                "floor was derived on 2026-08-29. Measured 2026-09-09 over the 7,970 "
                "distinct scored items in state/scores/ that carry a length from before "
                "the cut: 90 reach 3,000 words and 23 reach 5,000, so the new rung takes "
                "23 items and the rung below keeps 67 - 0.29 percent of items, about one "
                "item every three runs over the 77 runs in that ledger. Only the floor "
                "of the ask moves, because compression at a rung's floor is set by "
                "target_words_min and the ceiling cannot rise without moving "
                "evaluation.summary_words_max, which is what the pipeline agrees to "
                "publish and a separate decision. 5000 stays below the cut point of "
                "7,692, so this is still not the rung that asks for words the model "
                "never saw. Additive with a default, so an older config still validates "
                "and no read-side migration is needed (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-09-09T21:30",
            change=(
                "config/idhazh.json moves extract.truncation_cap_tokens from 5000 to "
                "10000. No field was added, removed or retyped. elements.max_per_article "
                "and finetune.sequence_length restate their arithmetic against the new "
                "cap; neither value moves."
            ),
            why=(
                "The cap is the largest quality lever nobody had pulled, and it was held "
                "shut by the window rather than by a measurement: at 8,192 the doubled "
                "cap did not fit. The window went to 16,384 earlier the same day, so it "
                "fits now. Measured 2026-09-09 over the 4,117 published items in "
                "state/item-health/2026-09.csv (2026-09-01 to 09, stock ubuntu-latest 4 "
                "vCPU runners): 36 of them, 0.87 percent, were cut at 5,000 tokens, and "
                "9 of them, 0.22 percent, would still be cut at 10,000. A cut article "
                "gains 23 to 5,000 tokens of prefill, median 1,616, and prefill runs at "
                "a median 9.85 tokens a second over those 4,117 rows, so the worst item "
                "pays about 8.5 more minutes against a summarize call that costs 114.6 s "
                "at the median and 312.7 s at the 95th. The prompt is 997 tokens plus "
                "1.306 a word by least squares over the same rows, so the worst case is "
                "about 14,100 tokens of a 16,384 window - 86 percent, a margin of 1.16x "
                "where it was 1.9x. The cap is fingerprint-digested, so every stamp "
                "moves and no summary written before today is comparable with one "
                "written after; that is correct, because the text the model read is not "
                "the same text. Guardrail #11 is untouched: extract sanitizes before it "
                "truncates, so a longer article is more untrusted text handled on "
                "exactly the terms the short one was."
            ),
        ),
        ChangelogEntry(
            version="2026-09-09T20:40",
            change=(
                "InferenceConfig.n_ctx now states what the window is and why the "
                "default stays 8192. No field was added, removed or retyped. "
                "config/idhazh.json moves models.summarize to n_ctx 16384 with "
                "flash_attention pinned on; models.visual_planner is unchanged."
            ),
            why=(
                "The field carried no description at all, so the one number in this "
                "block that decides whether a prompt fits was the only one with no "
                "reason beside it. The raise is the summarizer's alone: the visual "
                "planner is different weights with its own settings block since the "
                "roles were split, and nothing has measured a 16,384 window against "
                "it. Doubling buys nothing but KV cache - 32 KiB a token on those "
                "weights, so 0.25 GiB more - and run 2026-09-09-34323771996 read "
                "MemAvailable at 5.63 GiB at the tightest of 601 samples on a 15.61 "
                "GiB runner, which clears the 1.0 GiB bar 5.4 times over after the "
                "raise is paid. flash_attention is pinned in the same commit rather "
                "than a later one because n_ctx is fingerprint-digested and moves the "
                "stamp anyway, so pinning the flag beside it costs no second break in "
                "comparability. Pinning still earns its place: auto is a runtime "
                "autodetect that may resolve differently on other silicon, and a run "
                "that cannot say which kernel it used cannot be compared with one that "
                "can (Guardrail #10)."
            ),
        ),
        ChangelogEntry(
            version="2026-09-09T20:10",
            change=(
                "InferenceConfig gains log_verbosity, an optional llama-server -lv "
                "level. Null omits the flag and keeps the runtime default of 3. "
                "config/idhazh.json sets 4 on both model roles."
            ),
            why=(
                "The server was never asked to describe itself. At its default verbosity "
                "it prints twelve lines, and no line among them names flash attention, "
                "the KV buffer or the compute buffer - so every claim about what the "
                "runtime did with those settings was a claim about the flag we passed "
                "rather than about what happened (Guardrail #10). At 4 the model-loader block "
                "comes back and the log states the attention decision three ways: a "
                "named state, a compute buffer 5.1 times larger without fusion, and a "
                "graph 180 nodes longer. Measured 2026-09-09 on a 12th Gen Intel Core "
                "i7-1265U against llama.cpp b10444, eleven server starts, three runs an "
                "case, zero spread. It is a knob rather than a literal because an "
                "operator debugging a start wants 9 and a daily run does not (Guardrail #6), "
                "and it is set on both roles because both write a log nobody can read "
                "otherwise. What it costs is one job artifact growing from 1,085 bytes "
                "to about 16,011 - kept two days, committed never."
            ),
        ),
        ChangelogEntry(
            version="2026-09-09T18:00",
            change=(
                "observability gains six retention knobs, one per console payload that "
                "files by month: public_scores_keep_months, "
                "public_feed_health_keep_months, public_run_days_keep_months, "
                "public_day_metrics_keep_months, public_machine_keep_months and "
                "public_span_rollup_keep_months, each defaulting to 14. The three that "
                "project a state ledger must equal that ledger's own window, and all "
                "six are now checked by refuse_windows_shorter_than."
            ),
            why=(
                "The console is moving from inlining six committed ledgers into its "
                "document to fetching them, and a payload the pipeline appends to every "
                "run with no age is a directory that grows for ever (Guardrail #12). Every "
                "one is minted with a NON-NULL default in the same commit as its "
                "contract, because item_health_aggregate_keep_months and "
                "score_archive_keep_months are null today and a null that spreads stops "
                "reading as a decision. Fourteen is the number the two existing windows "
                "already carry: the console reaches 367 inclusive days and those days "
                "can fall in fourteen month shards. Adding them to full_grain_months() "
                "is what stops a knob being set narrower than a window preset can still "
                "select - a deleted shard blanks its panel silently, because a month "
                "with no file reads exactly like a month with no runs. Minted here "
                "rather than beside the producer so the producer, the consumer and the "
                "gates read one list instead of guessing at three (the shell-and-fetch "
                "migration, Fowler and Carmack, "
                "2026-09-08). appearance-config is NOT restamped beside this one: the "
                "only console key that row would have added, console.shimmer_after_ms, "
                "is minted in row 12 where it gets a measured value, so an entry here "
                "would record a change that did not happen."
            ),
        ),
        ChangelogEntry(
            version="2026-09-09T05:20",
            change=(
                "visuals.histogram_bins is now held between visuals.min_chart_points and "
                "visuals.max_chart_points. A config outside that window no longer loads."
            ),
            why=(
                "A histogram's bins are the marks a reader counts, so they are bounded by "
                "the two knobs that already say how many marks a chart may draw. Before "
                "this, a value above max_chart_points loaded and the validator admitted "
                "the plans asking for it, because enough_data counted the values being "
                "distributed rather than the bars drawn. The bin count is the same for "
                "every histogram in a run, so refusing it here says the fault once, to the "
                "operator who caused it, instead of refusing every histogram of every run "
                "and naming the article. Semantic narrowing with nothing to migrate: the "
                "committed config reads 3 and the tuned fixture 4, both inside the window."
            ),
        ),
        ChangelogEntry(
            version="2026-09-09T05:00",
            change=(
                "Added visuals.histogram_bins with a default of 3. Additive - a config "
                "written before this still validates and reads the default."
            ),
            why=(
                "A histogram's bars are counts rather than figures the article wrote, so "
                "something has to say how many bins its values fall into, and the model is "
                "the one thing that may not: it has no numeric field anywhere in its "
                "schema and the derived-value contract is what keeps it that way. Config "
                "rather than code because how coarse a distribution should be is a "
                "judgement an operator may hold a different view of, unlike where the "
                "edges fall, which is arithmetic and stays in idhazh.derived_values. The "
                "unit table's date-stamp was proposed for this block in the same pass and "
                "was refused - a stamp an operator can edit without editing the table it "
                "stamps is a stamp that lies, and every derived value that recorded it "
                "lies with it."
            ),
        ),
        ChangelogEntry(
            version="2026-09-09",
            change=(
                "Removed models.inference. Every models.<role> entry now carries its own "
                "inference block, and that block carries declared_for - the sha256 of "
                "the entry it is set for. A block whose declared_for is not the entry's "
                "sha256 is refused, and a config still spelling models.inference is "
                "refused by name."
            ),
            why=(
                "One settings block served two model families, so a swap of either entry "
                "inherited numbers measured against the other and nothing raised. It had "
                "already happened: the summarizer moved from the 8B to the 9B on "
                "2026-08-27 and the block did not move with it. Breaking, and the "
                "read-side answer is refusal rather than a lift onto the entries, "
                "because the lift is the inheritance - it would hand a swapped entry the "
                "previous weights' numbers in silence. config/ is human-edited, so the "
                "refusal names the block and the operator writes it once."
            ),
        ),
        ChangelogEntry(
            version="2026-09-08T16:49",
            change=(
                "Added drift.min_domain_rows, source_word_count_drop and "
                "extractiveness_rise with defaults. Existing configs remain readable."
            ),
            why=(
                "Issue 438 compared singleton domain samples and mixed model and scorer "
                "versions under a global row floor. Domain comparisons now need enough "
                "distinct measured articles. The existing length and copying thresholds "
                "move from code into config without changing their values."
            ),
        ),
        ChangelogEntry(
            version="2026-09-08",
            change=(
                "elements.max_per_article added, defaulting to 256 and at least 1. It "
                "bounds how many candidate elements one article's passes keep. Additive "
                "and optional with a default, so a config written before the section "
                "existed loads and behaves the same."
            ),
            why=(
                "The candidate pass keeps every quantity the number pattern matched, "
                "where the visual planner's own reader stops at 16, dedupes and drops. "
                "A pass with no bound at all is an unbounded table over fetched bytes "
                "(Guardrail #11), and a bound written into code is a tunable with no home "
                "(Guardrail #6). 256 is measured rather than guessed: it is above the "
                "densest committed page fixture extrapolated to an article at the "
                "truncation cap."
            ),
        ),
        ChangelogEntry(
            version="2026-09-07T03:00",
            change=(
                "collect.published_window_days added, defaulting to -1 for unbounded. A "
                "finite value must be strictly greater than collect.seen_window_days; -1 "
                "or anything above 90 is accepted today and everything else, including "
                "90 itself, is refused by name. The check sits on CollectConfig after "
                "validation, so raising seen_window_days past a finite cover fails the "
                "config too. Nothing reads the knob yet. Additive and optional with a "
                "default, so no read-side migration is needed - a config written before "
                "the field existed takes -1 and behaves exactly as it did."
            ),
            why=(
                "The published record is about to gain a lookback window, and the one "
                "mistake that window can make is a republication: an address the record "
                "has forgotten, whose first-sighting row expires in the same week, reads "
                "as first-seen-today and goes out as new. Equal is a hole rather than a "
                "bound, because at 90 and 90 both stores forget the same address on the "
                "same day and neither is left holding the evidence. The knob ships "
                "unbounded so the machinery lands switched off, and the schema is what "
                "makes the unsafe pairing unspellable rather than a comment asking an "
                "operator to be careful."
            ),
        ),
        ChangelogEntry(
            version="2026-09-07T02:00",
            change=(
                "finetune.prompt_iterations added, defaulting to 3 and at least 1. It "
                "bounds the offline write-critique-revise prompt loop "
                "(`backend/utilities/prompt_loop.py`): how many rounds it runs before it "
                "stops. Additive - a config without the knob takes the default."
            ),
            why=(
                "The summarizer prompt was argued in prose and never measured. The loop "
                "proposes a revised prompt with a model judge and an Editor rubric, then "
                "keeps it only when it beats the incumbent on the deterministic, "
                "model-free scorers over a frozen committed article set. The bound lives "
                "under finetune because it sizes an offline maintenance job that never "
                "runs on the runner, beside the corpus and prune schedules it sits with."
            ),
        ),
        ChangelogEntry(
            version="2026-09-07T00:30",
            change=(
                "summarize.key_point_restatement_ceiling added, defaulting to 0.5 and "
                "bounded above 0.0 and at most 1.0. to_summary now drops any key point "
                "whose share of four-word phrases already in the summary exceeds it, "
                "keeping the item and the surviving key points; the drop never falls "
                "below the band's key_points_min, so an item never loses its last key "
                "point. Additive: a config without the knob takes the default."
            ),
            why=(
                "The rule against a key point that only restates the summary was a "
                "sentence in the prompt, which gives the model no definition it can "
                "compute, and the restatement rate ran at seven in eight. A "
                "deterministic post-check makes 'restates' a measure code applies - the "
                "share of the key point's four-grams already in the summary - and drops "
                "the thin line rather than failing the item, because a restating key "
                "point is thin, not wrong."
            ),
        ),
        ChangelogEntry(
            version="2026-09-07",
            change=(
                "summarize.key_points_min and summarize.key_points_max moved off "
                "SummarizeConfig and onto each SummaryBand, and the min-not-above-max "
                "check moved with them onto the band. The committed ladder now grades "
                "the ask from one key point at the shortest band to five at the longest, "
                "where before every band was asked for two to five. A read-side migration "
                "distributes an older config's global key_points_min/max onto any band "
                "that lacks its own, then drops the global keys, so a config written "
                "before the move still loads."
            ),
            why=(
                "A 40-word summary of a 60-word post was asked for five key points on top "
                "of it - a request for facts the article does not hold, so the extra key "
                "points restated the summary. The count belongs on the band because a "
                "note carries one fact and an investigation carries several, and one "
                "global number cannot say both. Moving key_points_min too is forced: the "
                "shortest band's ceiling drops to one, below the old global floor of two, "
                "and the prompt reads both numbers off the same band."
            ),
        ),
        ChangelogEntry(
            version="2026-09-06T23:55",
            change=(
                "collect.source_yield_alarm_point added, defaulting to 0.5 and bounded "
                "above 0.0 and at most 1.0, and collect.source_yield_alarm_min_decisions "
                "added, defaulting to 30 and at least 1. Together they name, on a run's "
                "own summary, a source that answers cleanly and returns almost nothing. "
                "Additive: an older config validates and takes the defaults."
            ),
            why=(
                "Every existing signal asked whether we could ask, and none asked "
                "whether asking was worth it. scmp-news held permission allowed, "
                "availability answering and HTTP 200 with fifty dated entries every run "
                "for a fortnight while 123 of its 127 items failed extraction as "
                "paywalled - and reliability, which measures whether a feed answered, "
                "scored it 1.0. The ratio was already computed and already published; "
                "nothing applied a threshold and nothing spoke. Two knobs rather than "
                "one because a low yield and a low volume are independent axes, and a "
                "single number answering both fires on cnn-world at 1 of 7, which the "
                "source docs already ruled is a working feed."
            ),
        ),
        ChangelogEntry(
            version="2026-09-06T22:30",
            change=(
                "run.safety_ceiling_per_run default lowered from 160 to 80, and "
                "run.shard_timeout_minutes default raised from 150 to 200. Both are "
                "defaults on RunConfig; an older config that names either value keeps "
                "it."
            ),
            why=(
                "The ceiling is now an editorial cap: a day publishes half as many "
                "stories, and the 80 slots go to articles worth reading rather than to "
                "a duplicate or a badly-publishing feed (owner, 2026-09-05). The "
                "timeout rise is headroom for the coming two-call summariser change, "
                "not a response to a slower worker - at 80 items a worker draws 20 and "
                "the base work roughly halves; the bound is sized from the worst "
                "measured shard, 135.4 of the old 150 minutes over 80 rows on "
                "2026-09-02, not the median 78.5."
            ),
        ),
        ChangelogEntry(
            version="2026-09-06T21:40",
            change=(
                "collect.dedup_similarity_min added, defaulting to 0.94 and bounded to "
                "[0.0, 1.0], and collect.dedup_enforce added, defaulting to false. "
                "Together they drive a plan-stage pass that finds a day's same-story "
                "repeats across sources by cosine over headline-and-lead vectors. "
                "Additive: an older config validates and takes the defaults."
            ),
            why=(
                "The same story at two addresses was planned twice: the exact-url "
                "collapse only joins identical addresses, and two outlets carrying one "
                "story carry two addresses. The pass ships record-only (dedup_enforce "
                "false), so a day's duplicate rate is written to the run log and read "
                "before any cut is turned on. The threshold reuses "
                "assemble.duplicate_similarity_min rather than minting a second number "
                "for the same question one stage earlier."
            ),
        ),
        ChangelogEntry(
            version="2026-09-06T17:00",
            change=(
                "collect.reliability_window_days added, defaulting to 30 and refused "
                "below 30, and collect.reliability_floor added, defaulting to 0.5 and "
                "bounded above 0.0 and at most 1.0. Together they drive a per-feed "
                "reliability factor - productive reads over evidence-bearing reads in "
                "the trailing window - that scales a feed's authority inside "
                "rank.authority, clamped to [floor, 1.0]. Additive: an older config "
                "validates and takes the defaults."
            ),
            why=(
                "A feed that fails or parses to nothing kept scoring as though it had "
                "published, because authority read only its tier and its hand-set "
                "weight. The factor is derived from the committed feed-health record "
                "rather than hand-tuned, it only ever reduces (the clamp caps it at "
                "1.0), and a feed with no evidence in the window scores 1.0 so an "
                "untested or politely-refused feed is never punished. The window bounds "
                "the read (Guardrail #12) and the floor bounds the cut at two-to-one."
            ),
        ),
        ChangelogEntry(
            version="2026-09-06T16:00",
            change=(
                "observability.tracing_enabled default moves from false to true. A "
                "work shard now builds a span tree unconfigured, writes it to the "
                "committed trace under state/traces/, and folds it into the span "
                "rollup. The committed config sets the same value, so a fresh clone "
                "and the shipped file still agree."
            ),
            why=(
                "The owner turned tracing on by default (2026-09-06): the span tree "
                "and the committed rollup are worth their runner cost, which Carmack "
                "measured negligible. It is safe to run in CI because the sink is the "
                "committed file and nothing else - no host, no key - and the closed "
                "attribute vocabulary keeps article text out of every span (Guardrail #11). "
                "The move is additive: the committed config sets the value explicitly, "
                "so no persisted config changes meaning and no read-side migration is "
                "needed."
            ),
        ),
        ChangelogEntry(
            version="2026-09-06T15:00",
            change=(
                "observability.trace_window_days added, defaulting to 7. It bounds "
                "state/traces/, the raw span traces kept so an operator can open a "
                "recent run; a trace whose published day is more than that many days "
                "behind today is deleted whole. Additive - an older config validates "
                "and takes the default."
            ),
            why=(
                "Raw traces are evidence with a short life while the span rollup is the "
                "record, so the traces need a rolling window of their own. A trace is a "
                "lookup an operator opens, so it is deleted rather than folded - a fold "
                "would invent a total nobody reads. Seven days is measured at about "
                "0.6 MB a run over five runs a day, which bounds the tree at about "
                "21 MB whatever the project's age (Guardrail #12)."
            ),
        ),
        ChangelogEntry(
            version="2026-09-06T14:00",
            change=(
                "ui.read_mark_days moves from 7 to 14, and its meaning moves from 'the "
                "newest 7 dates the store holds' to '14 calendar days back from today'. "
                "ui.archive_recent_days moves from 7 to 14. console.window_presets "
                "gains a 1-day span and is now [1, 7, 14, 30, 90]; console.min_window_days "
                "moves from 7 to 1 so the new preset satisfies the existing range check. "
                "console.max_window_days keeps 366 and gains a description. Two fields "
                "are added: ui.offline_bytes_kept, defaulting to 20,000,000 and bounded "
                "at 2,000,000 and 100,000,000, and ui.archive_window_days, defaulting to "
                "30 and refused unless it names one of console.window_presets. The "
                "shapes are `UiConfig` and `ConsoleConfig`, which this document and "
                "`AppearanceConfig` share, so both schemas moved together. Every value "
                "legal before today is legal now and both new fields carry defaults, so "
                "a config written before today still validates and no read-side "
                "migration is owed."
            ),
            why=(
                "Read marks expired by position rather than by time. Keeping the newest "
                "7 dates the store happens to hold needs no clock, which was the point, "
                "but it bounds the store by how often a reader comes back instead of by "
                "how long ago they read: a reader who opens one day a month kept marks "
                "from seven different months, and each of them greyed out an article "
                "last seen most of a year ago. Fourteen calendar days trusts the device "
                "clock, which the old rule deliberately did not, and that cost is "
                "stated in the field itself rather than hidden - a clock set wrong now "
                "keeps marks too long or drops them early. A wrong mark is what the "
                "store exists to avoid, so the trade is taken (owner decision, "
                "2026-09-06). THE STATED RULE AND THE SHIPPED PRUNING ARE ONE COMMIT "
                "APART ON PURPOSE: this document is the contract for every row of "
                "TODO/20260906-constant-cost-reads-plan.md, so the knobs land once and "
                "no later row edits the config file. Row 4 of that plan changes "
                "frontend/src/lib/readstate.ts to prune by calendar. Until it merges "
                "the browser still keeps the newest 14 dates, which is a superset of "
                "the 14-day window and therefore never hides a mark a reader should "
                "still see. ui.archive_recent_days follows to 14 for the reason it "
                "matched read_mark_days at 7: a row in that block invites a reader back "
                "to a day, and a day whose marks were already dropped comes back "
                "looking unread. The presets gain one day because every span is a "
                "distinct fetch cost - a window pulls a month file per month it reaches "
                "- and there was no way to ask for the cheapest read of all, the run "
                "that has just finished. min_window_days drops to 1 to admit it. "
                "max_window_days does not move, and the description now says why: it is "
                "a retention floor rather than a viewport clamp, the only span control "
                "a reader can reach is the preset list, and lowering it would authorise "
                "deleting month shards the console can still ask for. "
                "ui.offline_bytes_kept exists because offline_days_kept cannot bound "
                "bytes: measured 2026-09-02 over the 12 served days, one day payload "
                "runs 8,231 to 1,373,593 bytes, a factor of 167, so fourteen days is "
                "anything from 115 KB to 19 MB. ui.archive_window_days names a span out "
                "of console.window_presets rather than declaring a second list of day "
                "counts, so the contract holds exactly one list of spans and the two "
                "surfaces cannot drift. Neither new knob has a reader yet; rows 8 and "
                "25 of the same plan are the readers."
            ),
        ),
        ChangelogEntry(
            version="2026-09-06T12:00",
            change=(
                "visuals.asset_base_url is added. It defaults to the empty string, which "
                "means this site, and is otherwise an absolute https prefix carrying no "
                "trailing slash, no query and no fragment."
            ),
            why=(
                "The published site has a 1 GB ceiling and the drawings are the part of it "
                "that grows with every day. This is the release valve for that: an "
                "operator names a host, the drawings a reader scrolls to are asked for "
                "there instead, and the bytes stop counting against the ceiling - one "
                "config edit rather than a project. It ships shut because nothing yet says "
                "the bytes must move, and opening it costs something measured: the "
                "candidate host caches for five minutes, so a repeat reader refetches, and "
                "the page's connect-src has to admit that one origin. Additive and "
                "backwards-compatible, so no read-side migration is owed - a config "
                "written before this loads on the default and every drawing is asked for "
                "at exactly the address it was asked for before."
            ),
        ),
        ChangelogEntry(
            version="2026-09-06",
            change=(
                "retention.pages_hard_cap_mb is added. It defaults to the 1024 MB the "
                "published-site gate already failed at, and is bounded ge=1, le=1024."
            ),
            why=(
                "The cap was a module constant in backend/idhazh/retention.py, so the one "
                "number that stops a deploy could not be read out of config or tightened "
                "without a source edit. The bound is what makes exposing it safe: config "
                "can only ever lower the cap, which is Guardrail #2's 'the budget is the "
                "platform, not a preference' held by the schema rather than by trusting "
                "nobody to edit a constant. Additive and backwards-compatible, so no "
                "read-side migration is owed - a config written before this loads on the "
                "default and the gate fires at exactly the size it fired at before."
            ),
        ),
        ChangelogEntry(
            version="2026-09-05T18:00",
            change=(
                "VisualKind, which types visuals.enabled_kinds, lost diagram and image. A "
                "config naming either value no longer loads."
            ),
            why=(
                "The diagram renderer went with the Mermaid round trip it read, and image "
                "never had a renderer at all (pseudo-plan row 63), so a config could ask "
                "for a kind nothing could draw. No read-side migration is owed: the "
                "committed config/idhazh.json names chart alone, which is the only value "
                "left, so the shipped file loads unchanged."
            ),
        ),
        ChangelogEntry(
            version="2026-09-05T14:00",
            change=(
                "models.route is renamed models.visual_planner, run.route_budget_minutes "
                "is renamed run.visual_planner_budget_minutes, and finetune.student now "
                "names visual_planner. finetune.teacher and finetune.student are typed "
                "ModelRole rather than Slug. Breaking: three key spellings changed. The "
                "read-side migration is a before-validator on ModelsConfig, RunConfig and "
                "FinetuneConfig that reads the old spelling as the new one and refuses a "
                "file carrying both with different values, so a config written before "
                "today still loads. No value moved: the weights, the revision, the sha256 "
                "and the 40 minutes are the numbers they were yesterday."
            ),
            why=(
                "Route names a dispatch decision and the stage names a planning "
                "decision, so every knob spelling it teaches the wrong word. It is paid "
                "now rather than later because twenty more plans are about to mint names "
                "against these keys, and each one would write the wrong name and then pay "
                "to change it (owner decision 2026-09-05). ModelRole replaces Slug "
                "because these two fields spell a key in models, a key in models is a "
                "Python attribute name, and an attribute name is snake_case - so Slug's "
                "kebab-case was a shape no key could ever have, and visual_planner would "
                "have been refused by the pattern before the check that matters ran. "
                "AppConfig already checks the name against the real block, so the pattern "
                "only has to bound the shape for an editor reading schemas/ offline."
            ),
        ),
        ChangelogEntry(
            version="2026-09-05T13:00",
            change=(
                "console.chart_height now defaults to 220 rather than 180 and "
                "console.chart_width to 760 rather than 600, and both carry a "
                "description naming their owner. The committed config/idhazh.json "
                "drops both keys; config/appearance.json keeps them. "
                "config/appearance.json drops assist.recall_min, which this document "
                "keeps at 0.68. The shapes are `ConsoleConfig` and `AssistConfig`, "
                "which this document and `AppearanceConfig` share, so both schemas "
                "moved together. A semantic shift on two defaults and nothing else - "
                "every value legal yesterday is legal today, and a config/idhazh.json "
                "written before today still declares the two console sizes and still "
                "wins over the new defaults through the frontend's middle merge "
                "layer, so no read-side migration is owed."
            ),
            why=(
                "Three keys were declared in both config files with two different "
                "values. The frontend merges the appearance block last, so the "
                "appearance file wins and the loser is silent. The two console sizes "
                "are drawn by the console pages and by nothing in backend/, so "
                "config/appearance.json owns them - the same rule that settled "
                "visual_side on 2026-09-05, and the rule backend/idhazh/config.py "
                "already follows when it reads console.max_window_days out of the "
                "appearance file. The defaults follow what ships: 220 and 760 are the "
                "numbers chart.height_px and chart.width_px already carry, raised from "
                "180 and 600 when the frame widened, so a fresh clone with no config "
                "would have drawn a console chart at a size no console page uses. "
                "assist.recall_min runs the other way. It is a gate on the ranking "
                "that only backend/tests/test_retrieval_eval.py reads, off this "
                "document, at 0.68; the frontend's AssistConfig does not declare the "
                "field, so the 0.61 in config/appearance.json had no reader at all. It "
                "was the value the bar held before it was re-derived against the "
                "pinned corpus on 2026-09-04, and 0.07 of drift is 10.3 percent of the "
                "live bar - worth nothing today and a wrong gate the day anything "
                "reads the appearance copy."
            ),
        ),
        ChangelogEntry(
            version="2026-09-05T12:00",
            change=(
                "ui.visual_side now defaults to trailing rather than above, and carries a "
                "description. The shape is `UiConfig`, which this document and "
                "`AppearanceConfig` share, so both schemas moved together. The value is "
                "dropped from the committed config/idhazh.json; config/appearance.json "
                "keeps it as digest.visual_side. A semantic shift on the default and "
                "nothing else - every value that was legal yesterday is legal today, so a "
                "file written before today still validates and owes no read-side "
                "migration."
            ),
            why=(
                "Two files declared one knob with two values: config/idhazh.json said "
                "above and config/appearance.json said trailing. That is the whole "
                "divergence between the two - the legacy ui block is a 16-key subset of "
                "the appearance digest block's 26, and visual_side was the only one of "
                "the 16 whose value disagreed. The published surface is drawn from "
                "config/appearance.json (docs/concepts/config.md), so the appearance file "
                "wins and the pipeline file drops its copy. The default follows the "
                "committed value because above is the one thing the page does not do: "
                "`DigestItem.svelte` renders the figure after the summary, so a fresh "
                "clone with no config would have resolved to a position no page renders."
            ),
        ),
        ChangelogEntry(
            version="2026-09-04T20:00",
            change=(
                "Added assist.eval_corpus_through, default 2026-08-26. Removed "
                "assist.recall_tolerance, added the same day and never released. "
                "assist.recall_min re-derived against the pinned corpus, 0.61 to 0.68."
            ),
            why=(
                "The retrieval gate scored against the live archive, so it measured the "
                "ranking and the publishing rate at once. The result list holds ten "
                "slots and the archive grew about 654 items a day, so every new item "
                "that outranked a gold item evicted it: the numerator eroded at "
                "-0.00004793 recall per published item while the denominator did not "
                "move. One publishing day shifted the instrument 39 percent of the "
                "eight-point effect the gate exists to catch, so no constant bar could "
                "survive - it failed twice in five days, the second time on a commit "
                "that changed one markdown file. The tolerance band bought 1.8 days and "
                "was the wrong shape; a band around a drifting number is a looser bar, "
                "not a stable one. Pinned, the drift term is zero, the bar rises from "
                "0.61 to 0.68, and it stops expiring. Ruled by Fowler and Carmack "
                "independently, 2026-09-04."
            ),
        ),
        ChangelogEntry(
            version="2026-09-04T18:00",
            change=(
                "Added assist.recall_tolerance, default 0.10. The retrieval gate now "
                "compares recall against recall_min x (1 - recall_tolerance) rather "
                "than against recall_min itself."
            ),
            why=(
                "recall@10 is measured over 60 queries with a standard error near "
                "0.046, so a bar at the measurement's own edge decides on noise. It "
                "failed on 2026-09-04 at 0.604 against 0.610 - inside the error bar - "
                "on a commit that changed one markdown file. The drift underneath is "
                "not a search regression: the gold set is frozen while the competitor "
                "set grows about 654 items a day, so a new item outscoring a gold item "
                "evicts it from the ten slots. At -0.00004793 recall per published "
                "item this band is worth 1,148 items, or 1.8 days - it buys time to "
                "pin the eval corpus, which is the fix, and it is deleted when that "
                "lands. Owner decision, 2026-09-04."
            ),
        ),
        ChangelogEntry(
            version="2026-09-03T18:00",
            change=(
                "collect.quarantine_after_failures removed, and the two "
                "observability names that were still readable in code - keep_months "
                "and hard_delete_after_months - removed with it. The rest rule now "
                "reads collect.availability_strikes_before_rest, and the telemetry "
                "fold reads observability.item_health_full_grain_months and "
                "observability.item_health_aggregate_keep_months. A config still "
                "spelling any of the three is refused, and the message names the knob "
                "to use instead."
            ),
            why=(
                "The three names were compatibility shims, kept readable only until "
                "every reader had moved. They have all moved, so keeping the shims "
                "means the emitted config says the same thing twice and an operator "
                "cannot tell which copy decides. No behaviour changes here and none "
                "could: the committed config carries 5 under both collect names and "
                "the tuned fixture carries 3 under both, so every reader reads the "
                "number it read yesterday. Refusing beats ignoring, because a knob an "
                "operator edits and nothing reads is a value they believe (Guardrail #6). "
                "The payload read migration for VerticalPlan.live_feeds stays, because "
                "a committed payload cannot be rewritten (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-09-02T22:00",
            change=(
                "observability.keep_months and observability.hard_delete_after_months "
                "removed, and six named ages added: item_health_full_grain_months 14, "
                "item_health_aggregate_keep_months null, feed_health_keep_months 14, "
                "scores_full_grain_months 14, score_archive_keep_months null and "
                "public_telemetry_keep_months 14. A config still carrying either old "
                "name loads and resolves to those defaults; carrying an old name "
                "beside its successor is refused. Every full-grain window is checked "
                "against the month shards console.max_window_days can select."
            ),
            why=(
                "One name covered state/item-health/ while state/feed-health/, "
                "state/scores/ and frontend/public/telemetry/ had no cleanup age at "
                "all, so three stores grew with nothing to stop them. Its value was "
                "also one shard short: the old check compared months * 30 against the "
                "console window instead of the shards that window selects, and a "
                "366-day read walks 367 inclusive days, which can fall in fourteen "
                "calendar months. The old value is read and dropped rather than "
                "carried forward, because it was chosen against a check that could not "
                "answer the question."
            ),
        ),
        ChangelogEntry(
            version="2026-09-02T20:00",
            change=(
                "collect.availability_strikes_before_rest, collect.availability_rest_runs, "
                "collect.feed_http_410_runs_before_retirement, "
                "collect.robots_denied_recheck_runs, "
                "collect.robots_unreachable_recheck_runs and "
                "collect.source_yield_min_complete_days added, defaulting to 5, 5, 5, 1, 1 "
                "and 30. Additive with defaults, so a config written before today still "
                "validates. Nothing reads them yet, and collect.quarantine_after_failures "
                "still decides every rest."
            ),
            why=(
                "The source lifecycle is four different questions - may we ask, does the "
                "address work today, is the address gone for good, and does the source "
                "publish anything worth reading - and one knob answered all of them. "
                "Naming each one first means the changes that read them are reviewable "
                "as behaviour rather than as a knob and a behaviour at once "
                "(docs/architecture/sources/health.md)."
            ),
        ),
        ChangelogEntry(
            version="2026-09-02T18:00",
            change=(
                "ui.offline_version, ui.offline_retired_through and ui.offline_days_kept "
                "added, defaulting to 1, 0 and 14. The shape is `UiConfig`, which this "
                "document and `AppearanceConfig` share, so both schemas moved together. "
                "Additive with defaults, so a config written before today still "
                "validates."
            ),
            why=(
                "The site ships a service worker, so a day a reader has already opened "
                "can be read again with no network. A worker is the only code this "
                "project ships that outlives the tab, so the switch that turns it off "
                "is a contract rather than a code edit: `offline_retired_through` "
                "retires every worker at or below the version it names, and a retired "
                "worker unregisters itself and deletes every cache it owns. "
                "`offline_days_kept` bounds what the worker keeps, because a cache that "
                "grows with the archive is the failure that argued against caching days "
                "at all (Guardrail #6, docs/concepts/ui-shell.md)."
            ),
        ),
        ChangelogEntry(
            version="2026-09-02T16:00",
            change=(
                "ui.desk_thin_max added, defaulting to 12, floored at 1. The shape is "
                "`UiConfig`, which this document and `AppearanceConfig` share, so both "
                "schemas moved together. Additive with a default, so a config written "
                "before today still validates."
            ),
            why=(
                "A desk now publishes why it ran what it ran, and one sentence under "
                "every desk would be a column of absences rather than information. This "
                "is the line between a desk that explains itself and a desk that says "
                "nothing, and a component may not spell it (Guardrail #6). Twelve is one "
                "page of the stream, so a desk under it is one a reader sees the whole "
                "of at once. Measured 2026-09-02 over the 12 committed days and 56 "
                "desk-days: 7 sit at or below it, 12.5 percent, and nothing in the "
                "record sits between 4 and 12."
            ),
        ),
        ChangelogEntry(
            version="2026-09-02T14:00",
            change=(
                "ui.rail_group_minutes added, defaulting to 60, bounded at 1 and 1440. "
                "The shape is `UiConfig`, which this document and `AppearanceConfig` "
                "share, so both schemas moved together. Additive with a default, so a "
                "config written before today still validates."
            ),
            why=(
                "The day's stories now run newest first down a time rail, and the rail "
                "draws one marker per group of stories rather than one per story. How "
                "coarse a group is decides how many times a reader is told the time, "
                "and a page may not spell that (Guardrail #6). Measured 2026-09-02 on Intel "
                "Core i7-1265U / Windows 11 / Python 3.14.2 over the 12 committed days "
                "and 4,713 stories, at the 60-minute default: 907 markers rather than "
                "4,713, so the rail leaves out 80.8 percent of the labels a "
                "marker-per-story rail would print. The busiest day, 2026-09-01, draws "
                "33 markers over 627 stories."
            ),
        ),
        ChangelogEntry(
            version="2026-09-01T20:00",
            change=(
                "ui.archive_recent_days added, defaulting to 7, bounded at 1 and 31. "
                "The shape is `UiConfig`, which this document and `AppearanceConfig` "
                "share, so both schemas moved together. Additive with a default, so a "
                "config written before today still validates."
            ),
            why=(
                "The archive listed every published day as a link and had nothing "
                "bounding it. At the 700 days this archive reaches in two years that "
                "is a wall of dates a reader has to scan past to get to the stories. "
                "It is now the newest few days as rows over one disclosure a month "
                "and one a year before this one, so the list a reader SEES grows "
                "twelve rows a year instead of 365. How many days stay out is a "
                "choice a page may not spell (Guardrail #6), and the ceiling is what makes "
                "the knob safe: set to 400 it is the wall again. Read by the build "
                "alone, so it never rides to a reader. What the DOCUMENT costs did not "
                "fall to nothing and is not claimed to: measured 2026-09-01 on Intel "
                "Core i7-1265U / Windows 11 / node 24.12.0, over two fixture archives "
                "of the same 24 months at 700 and 182 published days, gzip -9 of the "
                "prerendered /archive/ document, the page grew 11.05 bytes a day "
                "before and 8.0 after - 27.7 percent slower, not flat, because a link "
                "for every day is what a reader with no script uses to reach one "
                "(docs/reference/measurements.md)."
            ),
        ),
        ChangelogEntry(
            version="2026-09-01T18:00",
            change=(
                "page_weight.ceilings_bytes moved /console/ from 251,324 to 276,828, "
                "/console/model/ from 29,273 to 37,979 and /console/machine/ from "
                "31,714 to 39,743, in config/idhazh.json. No field moved and no "
                "default changed, so a config written before today still validates."
            ),
            why=(
                "The console chart-craft plan closed and all three numbers were "
                "derived on a tree twenty-six rows older. Nothing had crossed: the "
                "pages measured 142,623, 27,744 and 29,599 against ceilings of "
                "251,324, 29,273 and 31,714. What expired is the runway. A ceiling "
                "here is the heaviest of five builds plus seven published days at the "
                "measured per-day rate plus the 64-byte build noise floor, and "
                "/console/model/ had 1,529 bytes of slack left - 1.05 publishes - "
                "with /console/machine/ at 1.47. The raise decomposes into a page "
                "term and a rate term that sum to it exactly: +26,470 and -966 for "
                "/console/, +6,788 and +1,918 for /console/model/, +6,489 and +1,540 "
                "for /console/machine/. Measured 2026-09-01 on i7-1265U, Windows 11, "
                "node v24.12.0, twelve published days; see "
                "docs/reference/measurements.md."
            ),
        ),
        ChangelogEntry(
            version="2026-09-01T14:00",
            change=(
                "ui.filter_min_chars added, defaulting to 2. The shape is `UiConfig`, "
                "which this document and `AppearanceConfig` share, so both schemas "
                "moved together. Additive with a default, so a config written before "
                "today still validates."
            ),
            why=(
                "The day page's filter and the archive's topic pills became one panel, "
                "and the archive's field now narrows the loaded list as a reader types "
                "- so the same rule governs two surfaces and may not be spelled in "
                "either of them (Guardrail #6). Two rather than one because one letter "
                "narrows nothing: measured 2026-09-01 over the 12 committed days and "
                "4,203 story titles, the median single letter matches 80.2 percent of "
                "them and `e` matches 99.8 percent, against a median 0.8 percent for a "
                "two-letter pair."
            ),
        ),
        ChangelogEntry(
            version="2026-09-01T13:00",
            change=(
                "console.doubt_rows added, defaulting to 10. The shape is "
                "`ConsoleConfig`, which this document and `AppearanceConfig` share, "
                "so both schemas moved together. Additive with a default, so a "
                "config written before today still validates."
            ),
            why=(
                "The Summaries route now ranks sources by how often the faithfulness "
                "checker doubted their summaries, and an uncapped ranking is a page "
                "nobody reads to the end: measured 2026-09-01 over the committed "
                "score ledger, a thirty-day window holds 112 sources with a doubted "
                "summary. The cap is a knob rather than a literal for the same reason "
                "`source_rows` and `feed_rows` are (Guardrail #6), and it takes their "
                "default so three ranked lists on one console do not each end at a "
                "different depth."
            ),
        ),
        ChangelogEntry(
            version="2026-09-01T12:30",
            change=(
                "ui.leading_stories, ui.leading_per_desk, ui.leading_min, "
                "ui.lead_cluster_floor, ui.lead_shared_subject_weight and "
                "ui.lead_max_yesterday added, defaulting to 5, 2, 3, 3, 0.2 and 1. "
                "ui.items_per_topic is deprecated, read by nothing, and dropped "
                "from the committed file. The shape is `UiConfig`, which this "
                "document and `AppearanceConfig` share, so both schemas moved "
                "together."
            ),
            why=(
                "The day gets a leading block, and every number that decides it is "
                "a knob rather than a literal in a stage (Guardrail #6). The block "
                "replaces the three-per-topic headings, which on the 431-story day "
                "of 2026-08-30 drew 15 stories and put 416 behind five links - so "
                "items_per_topic lost its only reader. The field stays so a config "
                "written before today still validates, because an unknown key is "
                "refused; nothing reads it and the committed file no longer sets it "
                "(section 11). Every addition carries a default, so a file written "
                "before today still validates either way."
            ),
        ),
        ChangelogEntry(
            version="2026-09-01T10:00",
            change=(
                "ui.payload_slow_ms added, defaulting to 1200. The shape is "
                "`UiConfig`, which this document and `AppearanceConfig` share, so "
                "both schemas moved together. Additive with a default, so a config "
                "written before today still validates."
            ),
            why=(
                "The rest of a day is about to arrive by fetch, so for the first "
                "time a reading page can be waiting on something. What it shows "
                "meanwhile is one sentence past this number - never a spinner and "
                "never a bar, because the first frame is already readable and a "
                "compressed response cannot report a byte count worth printing. "
                "This is the one knob in the block only a browser reads: "
                "`shell_seed_items` is decided at build time and never told to a "
                "reader, and this one is the exact opposite, because the wait it "
                "bounds happens in the reader's browser."
            ),
        ),
        ChangelogEntry(
            version="2026-09-01T09:00",
            change="Added the assemble group and its duplicate_similarity_min knob.",
            why=(
                "The published day now groups its own items on the vectors it already "
                "carries, so a reader is not shown the same story eight times, and the "
                "cosine that decides it is a tuning knob rather than a literal "
                "(Guardrail #6). Its own group because `AppearanceConfig` imports "
                "`AssistConfig` whole: filing a build-time threshold there would "
                "publish it to a config the browser reads, where nothing can act on "
                "it. Additive with a default, so a config written before today still "
                "loads (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-09-01T02:00",
            change=(
                "console.source_rows and console.feed_rows added, both defaulting to "
                "10. The shape is `ConsoleConfig`, which this document and "
                "`AppearanceConfig` share, so both schemas moved together."
            ),
            why=(
                "Two console lists gained a cap on the same day, and a cap a "
                "component hardcodes is one an operator cannot move (Guardrail #6). The "
                "failure section now ranks sources by the articles their failures "
                "cost the digest; measured 2026-09-01 over the committed "
                "projection, a thirty-day window holds 60 sources with a loss, so "
                "an uncapped ranking is a list nobody reads to the end. The feed "
                "list had no cap at all and draws 26 of 182 checked feeds. "
                "Additive with defaults, so a config written before today still "
                "validates (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-09-01",
            change=(
                "ui.shell_seed_items added, defaulting to 15. The shape is "
                "`UiConfig`, which this document and `AppearanceConfig` share, so "
                "both schemas moved together. Additive with a default, so a config "
                "written before today still validates."
            ),
            why=(
                "A reading route's build-time load now splits a day into the facts "
                "that do not grow with the story count, the head of the published "
                "order, and the remainder. This number is where the head ends. "
                "Nothing fetches yet - the two halves are put straight back "
                "together, and the prerendered output is byte-identical - so the "
                "knob decides nothing today and everything once the item list "
                "moves to a browser fetch. Fifteen is the most items any reading "
                "surface draws before the reader acts, measured against the five "
                "desks `config/taxonomy.json` declares and `ui.items_per_topic`."
            ),
        ),
        ChangelogEntry(
            version="2026-08-31T23:59",
            change=(
                "ui.topic_pills_max added, defaulting to 8. The shape is `UiConfig`, "
                "which this document and `AppearanceConfig` share, so both schemas "
                "moved together. Additive with a default, so a config written before "
                "today still validates."
            ),
            why=(
                "The topic row was a horizontal scroll container, which is a control "
                "that hides its own contents; the owner ruled on 2026-08-31 that no "
                "reader-facing surface carries one. The row wraps now, and the topics "
                "past this number sit inside a `+N more` disclosure so a day with "
                "many topics does not turn the row into the page. A cap a component "
                "spells is a cap an operator cannot move (Guardrail #6)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-31T23:58",
            change="Added collect.max_source_share_per_day, and the committed config sets it.",
            why=(
                "Nothing counted one feed's contribution across a day. "
                "collect.max_per_source bounds a count inside one desk in one run, and "
                "a feed sits on exactly one desk, so a feed's ceiling for a whole day "
                "is that count times the runs the day had - 10 on a five-run day. A "
                "fixed count is a moving share: measured 2026-08-31 over the eleven "
                "committed days, 21 feeds held exactly 10 items of the 431-item day of "
                "2026-08-30, which is 2.32 percent each, while one feed held 1 of the "
                "four-item day of 2026-08-21, which is 25 percent. The share is what a "
                "reader sees and nothing bounded it. Additive with a default, so a "
                "config written before today still loads (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-31T23:55",
            change=(
                "ThemeChoice lost its `system` member and ui.theme_default now defaults "
                "to `dark`; the committed config repeats it. The shape is `UiConfig`, "
                "which this document and `AppearanceConfig` share, so both schemas "
                "moved together. Breaking: the enum is narrower. The read-side "
                "migration is a before-validator on `UiConfig.theme_default` that reads "
                "`system` as `dark`, so a config written before today still loads."
            ),
            why=(
                "The site now starts dark and light is an opt-in stored choice, so the "
                "three-state theme control became one button with two states (owner "
                "decision, 2026-08-31). `system` was never a theme - it was the absence "
                "of a choice - and nothing asks the device any more. Leaving the member "
                "in would let an operator set a value no surface can honour, which is a "
                "knob that silently does nothing. `dark` is the value `:root` carries "
                "in tokens.css, so the config and the first painted frame now agree "
                "instead of disagreeing."
            ),
        ),
        ChangelogEntry(
            version="2026-08-31T23:45",
            change=(
                "assist.recall_min default moved from 0.69 to 0.61, and the committed "
                "config repeats it. The shape is `AssistConfig`, which this document "
                "and `AppearanceConfig` share, so both schemas moved together."
            ),
            why=(
                "0.69 was two standard errors below a 2026-08-26 baseline of 0.767, "
                "and the baseline has slid to 0.690 since. The gate failed on main by "
                "0.00022, which is one percent of one standard error. It is not a "
                "ranking regression, and four cases over the same 60 queries, the same "
                "labels and the same ranking code say so. The archive at the last "
                "green commit scores 0.69163 +/- 0.04092. The same 3,485 items read "
                "with today's vectors score 0.69163 again, so the re-encode is "
                "+0.00000 and 0 of 10 committed day payloads changed a byte. The whole "
                "3,596-item archive held to that same denominator scores 0.68978, so "
                "competition is -0.00185. The whole archive as gated scores 0.68978 "
                "too, so the denominator is +0.00000 - unlike 2026-08-26 it cannot "
                "move, because the label set is frozen and already fully embedded. The "
                "entire drop is 111 new items competing for the same ten slots against "
                "labels pooled on 2026-08-26, which is the pooling bias "
                "docs/concepts/evaluation.md describes: 70.8 percent of filled slots "
                "now hold an item no labeller judged, against 65.6 percent then. The "
                "new bar comes off the same rule as the old one, 0.690 - 2 x 0.041 = "
                "0.607, rounded to two places as 0.61. The same rule applied at the "
                "last green commit also gives 0.61, so the number does not depend on "
                "which day it was taken. It buys about six published days at the "
                "measured slide of 0.0134 a day, and that expiry is written into the "
                "field description rather than left to be discovered by the next "
                "failing gate. Same field, same type: a config that names 0.69 still "
                "validates, so no read-side migration (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-31T23:00",
            change=(
                "observability gained cost_currency, cost_input_per_million and "
                "cost_output_per_million, all with defaults the committed config "
                "repeats. page_weight.ceilings_bytes moved /console/machine/ from "
                "6,899 to 30,391."
            ),
            why=(
                "The Machine route now draws the six panels rows 13 to 16 of the "
                "observability plan describe, one of which prices a run's tokens at a "
                "hosted provider's rate. That figure is a counterfactual and never a "
                "bill - nothing bills us, because Actions minutes are free on a public "
                "repository - and CLAUDE.md Guardrail #10 carries the owner's carve-out for "
                "it on the condition that the rate and its source are printed beside "
                "it. So the rate is a config knob and not a literal in a component "
                "(Guardrail #6), input and output are priced apart because a provider "
                "prices them apart, and the currency is named rather than assumed. "
                "The committed values are a documented starting point the owner has "
                "not yet set; docs/concepts/config.md says so. The ceiling moved "
                "because the route went from rendering no ledger to rendering nine "
                "panels: it is a ratchet and not a budget, re-derived from five builds "
                "with the heaviest per route, and no panel was cut to stay under the "
                "old number (owner ruling, 2026-08-31). Additive only - the model "
                "defaults and the committed file agree, and a config written before "
                "today still validates, so no read-side migration (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-31",
            change=(
                "page_weight.ceilings_bytes gained /console/model/ at 18,682 and "
                "/console/machine/ at 6,899 in config/idhazh.json, and /console/ moved "
                "from 259,908 to 250,643. PageWeightConfig now says a surface that "
                "splits into routes takes a ceiling per route. No field moved."
            ),
            why=(
                "The console became three prerendered routes, and one ceiling covering "
                "three surfaces cannot say which of them blew a budget - which is the "
                "decisive argument for routes over tabs, so the split is not finished "
                "until the ceilings follow it. The gate already fails a ceiling that "
                "names no route in the build; a route that names no ceiling is only "
                "reported, so two new surfaces would have grown unwatched. All three "
                "numbers are re-derived rather than carried over: heaviest of five "
                "builds, plus seven published days priced by removing a real one, plus "
                "the 64-byte noise floor, measured 2026-08-31 (measurements.md). "
                "/console/ came down because its model panels moved to a route of their "
                "own. Committed values only - the model default stays empty, the shape "
                "and the validation are unchanged, and every older config still "
                "validates, so no read-side migration (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-30T21:15",
            change=(
                "console.chart_rule_days, console.chart_minutes_target and "
                "console.chart_coverage_pct added, defaulting to 14 days, 6.0 "
                "minutes and 5 percent. The shape is `ConsoleConfig`, which this "
                "document and `AppearanceConfig` share, so both schemas moved together."
            ),
            why=(
                "Chart drawing is the only console section with a written decision rule "
                "in its own prose, and all three numbers in that rule were constants in "
                "a TypeScript module - so the one section that states a threshold was "
                "the one section an operator could not move a threshold on (Guardrail #6). "
                "The two limits are now markers on bars and the span is what decides "
                "whether a median is printed at all. Additive with defaults, so a "
                "config written before today still validates (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-30T20:00",
            change=(
                "console.band_outlier_rows added, defaulting to 10. The shape is "
                "`ConsoleConfig`, which this document and `AppearanceConfig` share, so "
                "both schemas moved together."
            ),
            why=(
                "The console's compression scatter became a per-day split plus a list "
                "of the summaries furthest from the length the prompt asked for, and a "
                "list that is capped needs the cap where an operator can move it. The "
                "scatter drew 2,740 marks in one colour, measured 2026-08-30, which "
                "rendered the dense middle as a block and hid the outliers - the only "
                "marks on it anybody could act on. Additive with a default, so a config "
                "written before today still validates (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-30T18:00",
            change="observability.tracing_enabled added, defaulting to false.",
            why=(
                "A work shard can now build a span tree, which is the one thing the "
                "three ledgers cannot hold: a start instant, a parent, and a step too "
                "small to earn a column. The robots read nests inside the fetch, and "
                "the prompt render and the reply parse sit either side of the model "
                "call, so a slow item finally says which of the five it was slow in. "
                "It is the only switch in this block that is off unconfigured, because "
                "it is the only instrument nothing reads: no page renders a span, no "
                "gate consults one, and a trace is evidence where a ledger row is the "
                "record (CLAUDE.md section 1b). Off is also what keeps CI clean - a "
                "publish job that could fail on a third party's availability is a "
                "worse job."
            ),
        ),
        ChangelogEntry(
            version="2026-08-30T16:00",
            change=(
                "observability.evaluation_enabled and observability.sample_rate now say "
                "which stage reads them and where the draw is recorded."
            ),
            why=(
                "Both fields described a behaviour that nothing performed: the block "
                "landed as config with no reader, so the scorer still took its decision "
                "from the command-line flag alone. Wiring them raised two questions the "
                "descriptions did not answer. A standing switch must not reach `validate` "
                "or `qualify`, because each refuses to run without a scorer and a "
                "config file would turn a deliberate measurement into an exit code. And "
                "a rate is unreadable a year later unless the run says which rate it ran "
                "under and whether it was drawn, so both now travel on the run manifest. "
                "No field was added, removed or retyped; only two descriptions changed, "
                "and every committed config still validates."
            ),
        ),
        ChangelogEntry(
            version="2026-08-30T14:00",
            change=(
                "The observability block added: evaluation_enabled, telemetry_publish, "
                "runtime_counters_scrape, sample_rate, keep_months and "
                "hard_delete_after_months."
            ),
            why=(
                "The pipeline had no way to turn a measurement off or to thin one, so "
                "every instrument was all-or-nothing at the command line and nothing at "
                "all in config (Guardrail #6). Three switches rather than one, because "
                "collection, scoring and publishing fail differently: state/scores.csv "
                "empties when the scorer will not load, the published telemetry file "
                "stops when a run does not publish, and state/runtime-counters.csv is "
                "silent when llama-server was gone before it was read. One master switch "
                "would leave a reader unable to say which of the three went dark. "
                "sample_rate is a rate over RUNS and is refused at zero, because a "
                "second way to say off is how two ways of saying it end up disagreeing. "
                "The item-health census is deliberately absent and the model says so: it "
                "is the denominator under every rate, so switching it off would make "
                "every other measurement unreadable rather than cheaper. Additive with "
                "defaults that reproduce today's behaviour exactly, so an older config "
                "still validates and no read-side migration is needed (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-30T12:00",
            change="Added drift.min_window_rows.",
            why=(
                "The drift review printed 'no drift across 0 recent and 0 baseline "
                "rows' and exited 0, because compare() walks the domains a window "
                "holds and an empty window holds none. Turn the scorer off for a "
                "week and the only automated watchman for slow extraction failure "
                "reports all clear every day, under a green check. The floor that "
                "separates 'nothing to compare' from 'no drift' is a tunable, not a "
                "literal (Guardrail #6). Additive with a default, so an older config "
                "still validates (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-30",
            change=(
                "Added collect.max_age_hours. collect.recency_weight's description now "
                "says it orders inside that window rather than deciding admission."
            ),
            why=(
                "Age was a bonus and never a gate, so nothing had a lower bound. "
                "Measured 2026-08-30 over the 2,900 items published between 2026-08-22 "
                "and 2026-08-29, aged at the moment their own run planned them: the "
                "median is 5.5 hours and the 90th percentile is 35.7 days. The oldest "
                "story the digest has published was 6,474 days old - a stock note from "
                "December 2008 - and 826 items (28.5 percent) were over a day old when "
                "they were added. They came from research-lab and institution feeds "
                "that serve a whole back catalogue, and the tier weighting scores an "
                "undated institution post at 1.0 against 0.64 for a three-day-old "
                "trade-press story, so the archive won. The argument for keeping age "
                "soft was that a cutoff wastes a slot on a quiet day. There are no "
                "quiet days: every run since 2026-08-25 has hit its ceiling, so each "
                "old item displaced a fresher one. Additive with a default, so an "
                "older config still validates (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-29T23:30",
            change=(
                "finetune.sequence_length default raised from 4096 to 8192, and "
                "finetune.holdout_days now states it must be shorter than the window "
                "has existed."
            ),
            why=(
                "Both were sized before the truncation cap moved, and running the "
                "pre-flight gates on 2026-08-29 showed both were wrong. 4096 was "
                "derived from a 1,923-word article; extract.truncation_cap_tokens is "
                "now 5,000 tokens, so the worst case is 920 + 5,335 + 900 = 7,155 and "
                "15 of 1,308 corpus rows already exceed 4096. Those rows would be "
                "truncated in training with no error, which teaches the model to stop "
                "mid-summary. The old text argued 8192 was headroom nothing uses; the "
                "measurement says it is the first power of two with a real margin, "
                "because 7168 clears the worst case by 13 tokens. Separately, "
                "holdout_days 14 over a window that had existed 7 days held out all "
                "1,308 rows and left nothing to train on, and split said so and exited "
                "0 anyway."
            ),
        ),
        ChangelogEntry(
            version="2026-08-29T23:00",
            change=(
                "console.window_presets added, and console.default_window_days must "
                "now be one of its members."
            ),
            why=(
                "The console had no way to say how many days it was showing, so every "
                "section picked its own span and one of them hard-coded seven days in "
                "the frontend. One control now sets one window for the whole page, and "
                "a control needs a list of the spans it offers. Four presets rather "
                "than a free number: a wider window fetches more month files, so every "
                "value is a distinct transfer cost and most of the values between "
                "these four cannot be told apart on the page. Additive with a default, "
                "so an older config still validates - the committed 30 is a member of "
                "the default list (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-29T22:00",
            change="Added collect.settled_failure_codes.",
            why=(
                "An address that failed was never recorded as published, so every later "
                "run of the same day planned it again. Measured over 2026-08-24 to "
                "2026-08-29: 403 repeat attempts inside a day produced 2 items, and 231 "
                "of the 233 repeated addresses never succeeded on any attempt. The codes "
                "listed cannot change before tomorrow; the ones left out - a rate limit, "
                "a reset connection, an unreachable model - can, so they still retry. "
                "Additive with a default, so an older config still validates "
                "(section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-29T20:00",
            change=(
                "finetune.reference_rows raised from 300 to 500, and "
                "finetune.reference_test_rows added."
            ),
            why=(
                "Owner decision, 2026-08-29. The size of the set and the size of its "
                "read-by-a-person slice were one number, which hid the only cost that "
                "matters: a row drafted with an expert model is about two minutes and a "
                "row read line by line is about five, so the split is what decides the "
                "hours. At 500 and 100 that is roughly 13 hours of drafting and 8 of "
                "reading, against the 12 the plan estimated for 300. Additive with a "
                "default, so an older config still validates (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-29T18:00",
            change=(
                "The finetune block added, and models.<role>.hf_base_repo added as an "
                "optional field."
            ),
            why=(
                "The training corpus needs its sizes and its two schedules in config "
                "before anything writes a row (Guardrail #6), and the window and the sample "
                "are two knobs rather than one because they price differently: the "
                "window costs 2.9 KB of compressed history per row and the sample costs "
                "GPU hours. The prune is two knobs for the same reason - how often it "
                "fires and how far back it keeps are independent, and 'prune quarterly' "
                "means neither one on its own. hf_base_repo sits on the model entry and "
                "not here because training reads the safetensors repository while the "
                "pipeline reads the GGUF one: held in two blocks, a model swap moves one "
                "string and leaves the other, and a LoRA adapter loads onto a mismatched "
                "base without raising, so the damage arrives as a quality drop nobody can "
                "attribute. Both additive with defaults, so an older config still "
                "validates and no read-side migration is needed (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-29T16:00",
            change=(
                "summarize.bands gained a fifth rung at min_source_words 3000, asking "
                "150 to 230 words. No existing rung moved."
            ),
            why=(
                "A 2,000-word article and a 3,846-word article were handed the identical "
                "ask, so one was compressed 10 to 1 and the other 19 to 1 for the same "
                "150-word midpoint. 3,846 words is what extract.truncation_cap_tokens of "
                "5000 lets through, so both are read whole and the difference is real "
                "text and not a guess about text. The floor is 3000 because that is the "
                "midpoint of the whole-read range, 2,923, rounded to a seam the ledger "
                "reports. Measured 2026-08-29 over the 445 rows of state/scores.csv that "
                "carry a trustworthy pre-cap length: 9 of them reach 3,000 words, which "
                "is 2.02 percent of items and 1 to 4 items a run over four runs of 107 "
                "to 117 items. This is the last rung there may be - a floor above the "
                "cut point would ask for words the model was never handed, and the "
                "model would fill the gap by elaborating the opening. 230 sits inside "
                "evaluation.summary_words_max of 250, so the gate did not move. "
                "Additive with a default, so an older config still validates and no "
                "read-side migration is needed (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-29T14:00",
            change=(
                "page_weight.ceilings_bytes gained /console/ in config/idhazh.json, and "
                "the description here stopped saying that route is unpriced. No field "
                "moved."
            ),
            why=(
                "The description said /console/ 'stays uncapped until somebody measures "
                "it', and this is that measurement. The page costs about 60 gzipped "
                "bytes a published item: removing one real mature day from every ledger "
                "the console reads and rebuilding cost 43,745, 43,704 and 36,504 bytes "
                "over 731, 724 and 621 scored items, measured 2026-08-29 on an Intel "
                "Core i7-1265U, Windows, node 24.12.0. So the headroom is three days of "
                "the heaviest of those, not the year /archive/ carries, and the number "
                "is meant to expire (Guardrail #10)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-29T09:00",
            change="evaluation.truncation_gap_max removed.",
            why=(
                "Its one caller stopped reading it in this commit, so the knob and its "
                "last reader go together and there is never a state where the number "
                "exists and nothing consults it. It set truncation_flagged from the gap "
                "between the two faithfulness scores, and that flag now carries "
                "Article.truncated - whether extract cut the body - because that is what "
                "its name says and what its one consumer prints. Retuning it was the "
                "alternative and it is not available: score_over_chunks takes the best "
                "of overlapping windows, a cut article's last window is not a window of "
                "the whole article, and the two window sets are not nested, so the gap "
                "can come out positive on an article that was never cut. Measured "
                "2026-08-28 over all 2,683 committed rows of state/scores.csv, the gap "
                "on the 22 genuinely cut rows runs -0.1235 to +0.0381 against this "
                "knob's 0.100 default - no value in that range separates a cut from "
                "chunk-boundary noise (Guardrail #10). "
                "BREAKING: EvaluationConfig forbids unknown keys, so a config file that "
                "still names this key fails to load with a message naming it. The "
                "read-side migration is the deletion of the key from config/idhazh.json "
                "in this same commit (section 11); a fork carrying its own config "
                "deletes one line. hhem, hhem_full and hhem_delta all stay - they answer "
                "what the cut cost, which is a different question."
            ),
        ),
        ChangelogEntry(
            version="2026-08-28",
            change=(
                "evaluation.chunk_words added, defaulting to 900, and "
                "evaluation.chunk_overlap_words added, defaulting to 150. Both were "
                "constants in backend/idhazh/evals/hhem.py. EvaluationConfig now refuses "
                "an overlap at or above the window."
            ),
            why=(
                "The faithfulness scorer's window size decides what premise every score "
                "was measured over, so it is a tunable and belongs in config (Guardrail #6), "
                "and scorer_version now spells it as window=900/150/anchored so a ledger "
                "row records the geometry that produced it. Neither default moves today: "
                "with 0 of 60 human labels drawn there is no ground truth to tune "
                "against, and a sweep would show only that the number moves, not which "
                "value is right (Guardrail #10). The guard exists because the chunker steps "
                "chunk_words - chunk_overlap_words and clamps that step to one word, so "
                "an overlap at or above the window walks a long article one word at a "
                "time - a job that never finishes rather than one that fails. Additive; "
                "an older config still validates and gets both defaults."
            ),
        ),
        ChangelogEntry(
            version="2026-08-27T21:00",
            change=(
                "evaluation.label_min_stratum_rows added, defaulting to 20, and "
                "evaluation.label_min_run_days now counts run-days at one scorer version "
                "rather than at one (scorer_version, pipeline_fingerprint) pair."
            ),
            why=(
                "The old rule was unreachable, not strict. The pipeline stamp digests "
                "seventeen inputs - a reworded prompt, a llama.cpp rebuild, a sanitizer "
                "fix - so shipping any summarize-side improvement reset the count to "
                "zero. Measured over the whole committed ledger on 2026-08-27: six "
                "distinct stamps across six scored run-days, and the longest unbroken "
                "run at one pair is three. Ten was never once reached. What is being "
                "calibrated is the scorer's cut, which lives inside scorer_version, so "
                "the pipeline is a covariate: it is reported per stratum and a stratum "
                "under label_min_stratum_rows is marked too thin to cut on. The trade is "
                "named rather than hidden - a pooled rate over several producers is a "
                "prior with wide bounds, never a calibration. Owner decision, 2026-08-27. "
                "Additive plus a widened meaning; an older config still validates."
            ),
        ),
        ChangelogEntry(
            version="2026-08-27T12:00",
            change=(
                "evaluation.verbatim_reject_ceiling added, defaulting to 0.75, and "
                "EvaluationConfig now refuses a value at or below "
                "evaluation.brief_compression_ceiling."
            ),
            why=(
                "Summarize had no rule that refused a summary which merely copies the "
                "source, so a brief published on 2026-08-26 was 44 words of which every "
                "word was one unbroken copy of its 53-word source - republishing an "
                "article body, which CLAUDE.md section 0a forbids outright. The number "
                "is a second knob rather than a reuse of brief_compression_ceiling: a "
                "refused item writes no score, so it leaves the corpus the brief-copying "
                "gate reads, and one shared number would have made that gate unable to "
                "fail. It sits in evaluation and not summarize because summarize is "
                "hashed whole into the pipeline fingerprint, and a rule that refuses a "
                "reply moves not one word the model writes. 0.75 is the midpoint of the "
                "empty band those eight brief items left - seven at or below 0.241, one "
                "at 1.000 - and it is a starting point, not a calibration (Guardrail #10). "
                "The invariant is the control: without it an operator editing one line "
                "silences the gate instead of tightening it. Additive with a default, so "
                "an older config still validates and no read-side migration is needed "
                "(section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-27T09:00",
            change=(
                "assist.search_min_days added, defaulting to 7, and "
                "assist.search_months restated as a floor rather than the whole scope."
            ),
            why=(
                "assist.search_months named a count of calendar shards, so the reach a "
                "search had was whatever the current month happened to hold - 31 days "
                "on 31 August and one day on 1 September. A reader who searched that "
                "morning got nothing back and could not tell it from a story we never "
                "published. A day floor makes the reach a promise instead of an "
                "accident, and capping the extra read at one shard keeps the cost "
                "bounded: measured 2026-08-26 the extra shard fires on 6 days of a "
                "30-day month and only when the shard already being read is small, so "
                "the bytes a search moves are levelled across the month rather than "
                "doubled. Additive with a default, so an older config still validates "
                "and no read-side migration is needed (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-27T05:00",
            change=(
                "page_weight.ceilings_bytes gained /archive/ again, at 7,553, and "
                "PageWeightConfig now says a route earns a ceiling when its growth is "
                "priced rather than when it does not grow."
            ),
            why=(
                "/archive/ was dropped on 2026-08-26 because it inlined every committed "
                "day, grew about 170 KB a publish, and was raised twice in one day to "
                "silence it - a countdown, not a bound. Search reads the month index "
                "now, so the page grows by one day link instead of by every story: "
                "measured 2026-08-27 at 2,906 bytes gzipped against 1,766,585 on main, "
                "and a year of publishing adds 4,476 more. With no ceiling the 99.8 "
                "percent saving had nothing holding it, and restoring the eager load "
                "would have passed every gate. Committed value only - the model default "
                "stays empty, the shape and the validation are unchanged, and every "
                "older config still validates, so no read-side migration (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-27T02:30",
            change="assist.search_months added, defaulting to 1.",
            why=(
                "Archive search used to rank over every committed day, because the page "
                "carried every committed day. It now reads month shards, so how many "
                "months it reads is a real choice and it was about to become a literal "
                "in the ranking module (Guardrail #6). One month, because the reader waits on "
                "the download and not on the arithmetic: measured 2026-08-26, a month of "
                "vectors is 518 KB and about 2.1 seconds on a 10 Mbit line at the rate "
                "the committed days ran, against 74 to 159 milliseconds of ranking, and "
                "three months is a 14.4 second download. Additive with a default, so an "
                "older config still validates and no read-side migration is needed "
                "(section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-27T02:00",
            change="ui.archive_page_size added, defaulting to 25.",
            why=(
                "The archive now lists every published story instead of a row per day, "
                "and a list of thousands needs a first screen. The number belongs in "
                "config rather than in the page (Guardrail #6). Additive with a default, so "
                "an older config still validates and no read-side migration is needed "
                "(section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-27",
            change=(
                "run.shard_timeout_minutes gained the derivation behind its 150, and "
                "digest.yml now reads the work job's timeout from it. Same field, same "
                "type, same value."
            ),
            why=(
                "The knob had no reader anywhere and said only 'derived from the "
                "WORST-case article'. digest.yml set the work job to 330 minutes, so "
                "config declared 150 while production ran 330 - a wrong answer with a "
                "schema behind it, and the number a model adoption sizes against. "
                "Reading the wall-clock of 106 work jobs over 27 runs settled which one "
                "was wrong: across 16 full days at four workers the slowest worker of a "
                "run took 83.5 to 117.5 minutes, and at today's item ceiling the worst "
                "was 94.5. 150 is half again that and 330 was 3.5x it, so the workflow's "
                "number moved and the config number did not. Description only, so every "
                "committed config still validates and no read-side migration is needed "
                "(section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26T21:45",
            change=(
                "page_weight.ceilings_bytes default is now empty, and /archive/ and "
                "/console/ are dropped from the committed config."
            ),
            why=(
                "The default duplicated the four numbers the gate reads from "
                "config/idhazh.json, so raising a ceiling meant editing two files a test "
                "then forced to agree - config is the single source now (Guardrail #6). "
                "/archive/ grows with every committed day and /console/ with the ledger "
                "its charts read, so their fixed ceilings failed on ordinary publishes "
                "rather than catching regressions; the gate now reports an unnamed route "
                "without failing it. Older config still validates and the empty default "
                "changes no committed value, so no read-side migration (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26T20:00",
            change="ModelRef gained an optional revision: the hub commit the weights are at.",
            why=(
                "Every weights download in the pipeline and the measurement harness read "
                "`resolve/main`, which is a branch. Upstream re-uploads a GGUF and the "
                "bytes change under a config that still records the old sha256, so a run "
                "either dies at the checksum or - where no checksum runs - measures a "
                "model nobody named (Guardrail #10). This field was rejected once as "
                "speculative because nothing read it; validate.yml now pins a revision "
                "and the adoption target names one, so it has readers. Optional with a "
                "null default, so the published run manifests that carry no revision "
                "still validate and no read-side migration is needed (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26T11:45",
            change="page_weight.ceilings_bytes['/archive/'] moved from 1,676,048 to 1,676,110.",
            why=(
                "The archive page now carries the search box, and a box costs bytes. "
                "Measured by building one tree twice on the same machine, same day "
                "payloads: with main's frontend /archive/ gzips to 1,675,988 and with "
                "the search box to 1,676,050, so the box costs 62 bytes against 60 of "
                "headroom. The new ceiling keeps the same 60-byte allowance the other "
                "three routes carry rather than rounding up to a number that would stop "
                "the gate firing. What the bytes buy is the input, its label and its "
                "empty state on the one page that can search the whole archive. Same "
                "field, same type: an older config still validates. A changed default, "
                "so it is stamped here (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26T11:20",
            change=(
                "assist.recall_min default moved from 0.85 to 0.69. "
                "assist.similarity_floor keeps 0.35 and carries a re-measured description."
            ),
            why=(
                "0.85 was calibrated against an archive where only 44.5% of items carried "
                "a vector, and the backfill took that to 99.9%. On the same 47 queries, "
                "the same labels and the same ranker, the number went 0.902 +/- 0.036 to "
                "0.743 +/- 0.042. That is not a ranking regression: holding the corpus to "
                "the same 944 items and swapping in the re-encoded vectors gives 0.910 "
                "+/- 0.034, so the vectors improved by 0.007. The whole effect is 1,175 "
                "items that the index could not see competing for the same ten slots "
                "(-0.142) plus a denominator that grew with coverage (-0.018). The new "
                "baseline over all 60 queries is 0.767 +/- 0.036 and the bar is two "
                "standard errors below it. It is a lower bound: 55.5% of the unlabelled "
                "items now holding a slot were unembedded when the labels were pooled, so "
                "nobody could have judged them, and they are counted as wrong answers. "
                "The floor does not move because the measurement says not to - the "
                "same-domain noise distribution is unchanged at 3.7x the pair count "
                "(p95 0.269 -> 0.2716, p99 0.399 -> 0.3992). Same fields, same types: an "
                "older config still validates and a committed config that names 0.85 "
                "still loads. A changed default, so it is stamped here (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26T10:10",
            change="Added the assist search knobs: similarity_floor, result_limit and recall_min.",
            why=(
                "Archive search had no measurement at all, and its two behavioural "
                "constants were literals in the ranking module with no override path "
                "(Guardrail #6). The floor was 0.20 and is now 0.35, which is a measured "
                "change rather than a preference: at 0.20 every one of eight off-domain "
                "probe queries returned results - one of them eighteen - so 'Nothing in "
                "the archive is close to that' was a promise the selector could not keep. "
                "Measured 2026-08-26 on the committed archive over 60 hand-labelled "
                "queries: the floor cuts surviving non-answers from 11.4% to 1.9% and "
                "costs 0.035 of reachable recall@10, which is inside one standard error. "
                "recall_min is the regression bar the new backend eval enforces. All "
                "three are additive with defaults, so an older config still validates and "
                "no read-side migration is needed (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26T10:05",
            change="Added the assist block: max_tokens and min_readable_letter_share.",
            why=(
                "The encoder's token cap was a literal in embed.py, which is exactly the "
                "kind of tunable Guardrail #6 puts in config. The second knob is new "
                "behaviour: an item the encoder cannot read used to get a confident "
                "vector no query could retrieve, and now gets no vector and a logged "
                "reason. Both defaults are measured, not chosen - see the field "
                "descriptions. Additive with defaults, so an older config still "
                "validates and no read-side migration is needed (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26T10:00",
            change="Added the page_weight block.",
            why=(
                "A prerendered page could grow without limit and nothing said so. The "
                "marker count in payload-weight.spec.ts catches a day payload inlined "
                "where no day is rendered; it cannot see /archive/, which inlines every "
                "day on purpose, and it cannot see growth that carries no marker. A "
                "ceiling per route catches both. It is a knob rather than a literal in "
                "the gate script (Guardrail #6). Additive with a default, so an older config "
                "still validates and no read-side migration is needed (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26",
            change=(
                "run.safety_ceiling_per_run default moved from 200 to 160. "
                "run.max_parallel gained a description."
            ),
            why=(
                "The ceiling is the worst case every downstream bound has to clear, and "
                "200 cleared neither of them. digest.yml now derives the automatic work "
                "fan-out as min(ceil(items / run.shard_size), run.max_parallel), so at "
                "the ceiling a worker draws 50 items across the four workers a scheduled "
                "run gets. Against the Qwen3.5-9B candidate that is 318 derived minutes "
                "by length interpolation and 345 by decode ratio, over a 330-minute work "
                "timeout that nobody may raise (Guardrail #2); at 160 the same arithmetic "
                "gives 40 items, 254 and 276 minutes. The route stage says the same "
                "thing from the other side: its measured slow-host ceiling is 166 items "
                "at a 50-minute budget (2026-08-25, six runs, 703 items), so 200 and the "
                "router never agreed and 160 does. The largest day ever planned is 149 "
                "items (run 32742672105, 2026-08-24), so 160 removes nothing that has "
                "ever been read. run.max_parallel had no description at all while being "
                "the bound the derivation clamps by, and it is deliberately four while "
                "digest.yml lets an operator dispatch eight. Same fields, same types, "
                "same units: an older config still validates, and a committed config "
                "that names 200 still loads. A changed default, so it is stamped here "
                "(section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-25T19:30",
            change="Added models.inference.metrics, on by default.",
            why=(
                "A run could not say how close it came to the context wall, and no "
                "number said whether more than one slot was ever busy. llama-server "
                "counts both already and only publishes them under --metrics. The flag "
                "is a knob rather than a workflow literal (Guardrail #6), and the endpoint "
                "it opens is llama-server's own loopback surface inside a CI job, so no "
                "reader is served by it and Guardrail #1 is untouched. Additive with a "
                "default, so an older config still validates and no read-side migration "
                "is needed (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-25T18:00",
            change="Added console.chart_width.",
            why=(
                "Every console chart is prerendered, so on the server there is no element "
                "to measure and the chart needs a width given to it. Without one each "
                "chart drew into an arbitrary viewBox and let the browser stretch it: "
                "measured 2026-08-25 at a 1057px window, one page scaled the same "
                "font-size to 4.5px in one panel and 16.6px in the next. Additive with a "
                "default, so an older config still validates and no read-side migration "
                "is needed (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-25",
            change=(
                "run.route_budget_minutes now stops the route stage instead of warning it, "
                "and visuals.enabled_kinds defaults to chart alone."
            ),
            why=(
                "Warning after the fact never saved a day. Measured on ubuntu-latest over "
                "six runs on 2026-08-24/25 (703 routed items): the mean per-item cost is "
                "20.7 s on a fast host and 40.3 s on a slow one, so a 145-item day needs "
                "50 to 97 minutes against a 60-minute job. Four of the six runs were "
                "cancelled at the bound, and a cancelled job skips its upload step - so "
                "every decision the hour bought was discarded and the day published with "
                "zero visuals. Diagram drawing is what made the existing pre-filter "
                "unfireable: it is reachable for every item by construction, so the model "
                "was asked about 145 of 145 items on 2026-08-25 while it drafted zero "
                "diagrams in 88 and rendered zero in 703. With it off, 68 of those "
                "145 items (46.9%) never reach the model at all. Same fields, same types, "
                "same units; an older config still validates. Semantic shift on one and a "
                "changed default on the other, so both are stamped here (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-24T23:40",
            change=(
                "Added evaluation.labellers, evaluation.label_draw_per_decile and "
                "evaluation.label_min_run_days."
            ),
            why=(
                "The faithfulness cuts are a reader-facing promise with no measured error "
                "rate behind them, and the missing instrument was labels rather than more "
                "rows. The draw size and the collection floor are tuning decisions, not "
                "literals (Guardrail #6). `labellers` is empty by default, so a fresh clone can "
                "draw the queue and read it but cannot record a verdict - and because the "
                "row has no author field a model could fill, that list is a structural "
                "control rather than a discouragement. Additive with defaults."
            ),
        ),
        ChangelogEntry(
            version="2026-08-24T23:10",
            change=(
                "Added visuals.request_timeout_minutes, visuals.lead_words and "
                "run.route_budget_minutes."
            ),
            why=(
                "The route stage crossed its 60-minute job bound on five of the last "
                "eight runs. Measured on ubuntu-latest 2026-08-24 (run 32742672105): "
                "fixed cost 47 s, stage 3155 s, 149 items at a mean of 21.0 s. So "
                "per-item inference owns the time, not model load. The router had no "
                "request budget of its own and borrowed run.shard_timeout_minutes - "
                "150 minutes against a 60-minute job, which can never fire. lead_words "
                "was a literal on the hot path and is most of each request's prefill. "
                "The route budget warns before the bound instead of after it. All three "
                "are additive with defaults, so an older config still validates."
            ),
        ),
        ChangelogEntry(
            version="2026-08-24T21:40",
            change="Added ui.items_per_topic and console.failure_list_max.",
            why=(
                "Both are the same defect at two altitudes: a page that renders every "
                "row it holds. 586 items in one queue gave the day page a first screen "
                "chosen by whichever topic id sorts first, and 800 failed rows measured "
                "7824 pixels and pushed the compression chart off the operator's reach. "
                "How many to show first is a tuning decision, not a literal (Guardrail #6). "
                "Both are additive with defaults, so an older config still validates."
            ),
        ),
        ChangelogEntry(
            version="2026-08-24T11:15",
            change="Added collect.blocked_url_markers, empty by default.",
            why=(
                "A working news feed syndicated affiliate credit-card pages, which "
                "published at 0.92 to 0.95 faithfulness and banded high. The summaries "
                "were faithful - that is the point. Short declarative marketing prose is "
                "trivially entailed, so no faithfulness threshold detects it at any cut "
                "and raising the bar rewards it. The control has to sit where the item is "
                "collected, before anything is spent on it (Guardrail #2)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T19:50",
            change=(
                "Added the brief summary band, lowered evaluation.summary_words_min to 25, "
                "lowered extract.min_source_words to its derived value, added "
                "evaluation.brief_compression_ceiling, and added line-shape prose knobs."
            ),
            why=(
                "Short sources should publish with an honest brief instead of being padded "
                "or dropped. The old word gate forced the decoder to keep writing on a "
                "small source, which made invention more likely."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T19:40",
            change="Added the console block for the interactive telemetry viewport.",
            why=(
                "The console now lets the operator pan and zoom over the published "
                "item-health projection, so the default window, pan step, zoom factor, "
                "minimum denominator and chart size are tunable config values (Guardrail #6)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T19:35",
            change="Added llama-server runtime-sweep knobs to models.inference.",
            why=(
                "The runtime sweep must change one measured flag at a time through config, "
                "not through workflow literals. The startup_warmup default matches the "
                "current digest workflow, so the fingerprint input describes the server "
                "that actually runs."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T18:15",
            change=(
                "Added extract prose-shape, enforcement and paywall-marker knobs; changed "
                "extract.min_source_words to a brief-tier threshold."
            ),
            why=(
                "Extraction now records short or list-shaped pages instead of dropping "
                "them by length, while publisher-declared paywalls still stop publication. "
                "The new thresholds and switches are tunable config values (Guardrail #6)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T17:52",
            change="Added models.inference.request_timeout_minutes.",
            why=(
                "One hung summarizer request was using the whole shard timeout, so a "
                "single bad item could burn 150 minutes and hide the cause. The new "
                "per-request budget is sized from the measured worst 8B long article "
                "plus a cold prompt prefix, doubled, while run.shard_timeout_minutes "
                "stays the outer bound. Additive - an older config still validates."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T17:41",
            change="Added evaluation.lead_coverage_min.",
            why=(
                "Lead coverage now caps a high confidence band at medium. The threshold "
                "is a tunable band input, so it belongs in config rather than in score.py "
                "(Guardrail #6). Additive - an older config still validates through the "
                "schema default."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T16:00",
            change="Added ui.read_mark_days.",
            why=(
                "Read marks were one flat list of item ids that never expired, so an id "
                "reused on a later day greyed out an article the reader had never "
                "opened, and the store grew for ever. Marks are now held per digest "
                "date and pruned to the newest days this number allows. Additive - an "
                "older config still validates, and the browser drops the old flat list "
                "on sight because there is no honest way to tell which day those ids "
                "belonged to."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T15:00",
            change="Added summarize.title_words_min and summarize.title_words_max.",
            why=(
                "The digest published the source's own headline, which is written to "
                "win a click rather than to say what happened. The summarizer now "
                "writes the title too, and the range it is asked for is a knob like "
                "every other length in this block (Guardrail #6). Additive - an older "
                "config still validates, and an item whose title misses the range "
                "falls back to the source's."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23",
            change="Added the summarize block: length bands, key-point range and quote cap.",
            why=(
                "The lengths the prompt asks for were literals inside the prompt text, "
                "where no schema could see them and nothing checked them against the "
                "range the pipeline accepts (Guardrail #6). They are bands rather than "
                "one range because a release note and a long read asked for the same "
                "number of words gives a padded summary of the first and a thin one of "
                "the second. Moving them here also puts them inside the prompt string "
                "the fingerprint hashes, so changing what we ask for now re-summarizes "
                "rather than reusing a cached reply written under the old ask. "
                "Additive - an older config still validates."
            ),
        ),
        ChangelogEntry(
            version="2026-08-22T11:00",
            change=(
                "Replaced run.item_cap_per_day with run.safety_ceiling_per_run. Added "
                "collect.recency_weight, collect.recency_half_life_hours, "
                "collect.max_future_hours and collect.seen_window_days. Raised "
                "inference.max_output_tokens to 900."
            ),
            why=(
                "A daily cap decided the size of the day; supply and the ranking should. "
                "The ceiling that remains is a crash guard against a mis-parsed feed. "
                "Recency is a bonus rather than a cutoff so a strong older item is never "
                "dropped for a weak new one. The token stop is labelled as the crash "
                "guard it always was, and sized so the prompt sets the length."
            ),
        ),
        ChangelogEntry(
            version="2026-08-22T09:00",
            change="Removed collect.min_feeds_floor.",
            why=(
                "Nothing read it. The floor a vertical is actually held to is its own "
                "min_feeds in taxonomy.json, so a second number calling itself the "
                "default described a mechanism that does not exist."
            ),
        ),
        ChangelogEntry(
            version="2026-08-22",
            change="Added the visuals block.",
            why=(
                "Routing needs its bounds and its enabled-kinds gate in config before the "
                "router may choose a kind. Additive - an older payload still validates."
            ),
        ),
        ChangelogEntry(
            version="2026-08-21T06:00",
            change="Added the ui block.",
            why="The published surface's knobs need a home before a component reads one.",
        ),
        ChangelogEntry(
            version="2026-08-21T05:00",
            change="Added collect.max_per_source.",
            why=(
                "The first live run planned a whole vertical from one blog: with no story "
                "carried twice, the tie-break decided the day and one source won it."
            ),
        ),
        ChangelogEntry(
            version="2026-08-21T03:00",
            change=(
                "Replaced evaluation.compression_min/max with summary_words_min/max; added "
                "extract.min_source_words and extract.boilerplate_ratio_max."
            ),
            why=(
                "At a fixed output budget a compression ratio measures the article's length, "
                "not the summary's quality - it would have flagged every short article "
                "forever. Absolute word bounds detect the two real failures directly."
            ),
        ),
        ChangelogEntry(
            version="2026-08-21",
            change="Initial shape: run, collect, extract, models, evaluation, drift, retention.",
            why="Contracts before logic - no stage may reach for a tunable that has no home.",
        ),
    )

    run: RunConfig = Field(default_factory=RunConfig)
    collect: CollectConfig = Field(default_factory=CollectConfig)
    extract: ExtractConfig = Field(default_factory=ExtractConfig)
    elements: ElementsConfig = Field(default_factory=ElementsConfig)
    models_file: ModelsFile = Field(
        default="models/qwen3.5-9b-q4km.json",
        description=(
            "Which file under config/models/ holds the active model. The whole swap: "
            "every fact about a set of weights - the repository, the digest, the window "
            "they were measured in, the markers their server renders - lives in the "
            "file this names, so pointing at another committed file swaps the model and "
            "pointing back reverts it, with the previous model's measured numbers still "
            "on disk rather than in git history. It carries a default naming the "
            "committed file so a fresh clone runs unconfigured (Guardrail #6)."
        ),
    )
    summarize: SummarizeConfig = Field(default_factory=SummarizeConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)
    drift: DriftConfig = Field(default_factory=DriftConfig)
    retention: RetentionConfig = Field(default_factory=RetentionConfig)
    visuals: VisualsConfig = Field(default_factory=VisualsConfig)
    assemble: AssembleConfig = Field(default_factory=AssembleConfig)
    placement: PlacementConfig = Field(default_factory=PlacementConfig)
    lens_weights: LensWeightsConfig = Field(default_factory=LensWeightsConfig)
    ui: UiConfig = Field(default_factory=UiConfig)
    assist: AssistConfig = Field(default_factory=AssistConfig)
    console: ConsoleConfig = Field(default_factory=ConsoleConfig)
    page_weight: PageWeightConfig = Field(default_factory=PageWeightConfig)
    finetune: FinetuneConfig = Field(default_factory=FinetuneConfig)
    reference_dataset: ReferenceDatasetConfig = Field(default_factory=ReferenceDatasetConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)

    @model_validator(mode="before")
    @classmethod
    def _a_removed_top_level_block_is_refused_by_name(cls, data: Any) -> Any:
        """`models` left this file on 2026-09-14 and is answered by name.

        The read-side migration `CLAUDE.md` section 11 owes for the removal. A
        config that still carries the block would otherwise fail with "extra
        inputs are not permitted", which does not tell an operator that their
        eleven lines are now a file and a pointer.
        """
        return refuse_a_removed_knob("config", data, SUPERSEDED_APP_NAMES)

    @model_validator(mode="after")
    def _the_ladder_and_the_extract_floor_agree(self) -> Self:
        """The ask and the tolerance now live together, so only one block pair is left.

        Until 2026-09-09 this checked every band against two global word bounds in
        `evaluation`. That check is gone with the bounds: the tolerance is derived
        from the band it applies to, so an operator editing the ladder can no
        longer put the ask outside the gate without seeing both. What remains is
        the one derivation that genuinely spans two blocks - the shortest ask sets
        the shortest article worth fetching.
        """
        brief_target = self.summarize.bands[0].target_words_min
        derived_floor = math.ceil(brief_target / self.evaluation.brief_compression_ceiling)
        if self.extract.min_source_words != derived_floor:
            raise ValueError(
                "extract.min_source_words must equal summarize.bands[0].target_words_min "
                "divided by evaluation.brief_compression_ceiling"
            )
        return self

    @model_validator(mode="after")
    def _finetune_names_models_that_exist(self) -> Self:
        """A role that names no model is a training session that downloads nothing.

        Checked here because `FinetuneConfig` cannot see `models` and a typo
        would otherwise surface on a GPU somebody is paying for, hours later.

        A role still naming a retired one is answered by name. `visual_planner`
        and its older spelling `route` are the two that were legal, and the
        difference matters to whoever is reading the failure: they did not
        misspell a key, the model is gone.
        """
        roles = set(ModelsConfig.roles())
        named = self.finetune.teacher
        if named in SUPERSEDED_MODELS_NAMES:
            raise ValueError(
                f"finetune.teacher names {named}, a model that was retired with the "
                "visuals stage. Name one of models: " + ", ".join(sorted(roles))
            )
        if named not in roles:
            spelled = ", ".join(sorted(roles))
            raise ValueError(f"finetune.teacher must name one of models: {spelled}")
        return self

    @model_validator(mode="after")
    def _the_archive_opens_on_a_span_the_presets_name(self) -> Self:
        refuse_an_archive_window_no_preset_offers(self.ui, self.console)
        return self

    @model_validator(mode="after")
    def _no_cleanup_age_is_shorter_than_the_console_can_ask_for(self) -> Self:
        """Every full-grain window outlives the widest read the console offers.

        Checked here because `ObservabilityConfig` cannot see `console`, and the
        failure is the worst kind: a shard is deleted, a reader pans back to it
        months later, and the page draws a gap that reads as a day the pipeline
        did nothing. `config.load` runs the same check again against
        `config/appearance.json`, which is the file the published console
        actually reads its window from.
        """
        self.observability.refuse_windows_shorter_than(
            months_a_window_can_touch(self.console.max_window_days),
            window_days=self.console.max_window_days,
        )
        return self
