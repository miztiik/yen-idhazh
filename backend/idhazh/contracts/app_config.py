"""`config/idhazh.json` - the one tree every block hangs from, and the rules that cross two of them.

One block's knobs live in `idhazh.contracts.knobs.<block>`. This file holds the
aggregate and the six validators no single block can run, because each of them
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
from idhazh.contracts.knobs.bench import BenchConfig
from idhazh.contracts.knobs.collect import CollectConfig
from idhazh.contracts.knobs.console import ConsoleConfig
from idhazh.contracts.knobs.evaluation import DriftConfig, EvaluationConfig
from idhazh.contracts.knobs.extract import ElementsConfig, ExtractConfig
from idhazh.contracts.knobs.finetune import FinetuneConfig, ReferenceDatasetConfig
from idhazh.contracts.knobs.models import SUPERSEDED_MODELS_NAMES, ModelsConfig, ModelsFile
from idhazh.contracts.knobs.observability import LoggingConfig, ObservabilityConfig
from idhazh.contracts.knobs.page_weight import PageWeightConfig
from idhazh.contracts.knobs.placement import (
    SECONDS_A_CALL,
    AssembleConfig,
    LensWeightsConfig,
    PlacementConfig,
)
from idhazh.contracts.knobs.prune import PruneConfig
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
            version="2026-09-19",
            change="observability.runtime_counters_scrape, removed with the ledger it named.",
            why="No code ever read it, so setting it false changed nothing.",
        ),
        ChangelogEntry(
            version="2026-09-18T11:00",
            change="The three extract.chrome_* knobs, removed with the store they governed.",
            why="Over a full run the store moved the boilerplate signal zero times.",
        ),
        ChangelogEntry(
            version="2026-09-18T10:00",
            change="adaptive_dedup_threshold.judge_temperature, additive, default 0.0.",
            why="The swap reads position bias only while the sampler adds no noise of its own.",
        ),
        ChangelogEntry(
            version="2026-09-18T09:00",
            change="adaptive_dedup_threshold and run.judge_shard_timeout_minutes, additive.",
            why="The merge line was set by one reading and nothing re-read it.",
        ),
        ChangelogEntry(
            version="2026-08-21",
            change="Earlier changes are in this file's git history.",
            why="A changelog says what moved lately; git is the archive.",
        ),
    )

    run: RunConfig = Field(default_factory=RunConfig)
    bench: BenchConfig = Field(default_factory=BenchConfig)
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
    prune: PruneConfig = Field(default_factory=PruneConfig)
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

    @model_validator(mode="after")
    def _a_day_of_judging_fits_inside_one_leg(self) -> Self:
        """A budget a leg cannot finish is a job GitHub kills with nothing uploaded.

        Checked here because it reads `assemble.same_story` and `run`, which are
        two blocks, and `AppConfig` is the lowest model holding both. The
        refusal prints the arithmetic rather than a bare comparison: a person
        raising the budget has three knobs to choose between, and the message
        has to say which.
        """
        knobs = self.assemble.same_story.adaptive_dedup_threshold
        a_leg = math.ceil(knobs.pair_budget / knobs.shards)
        seconds = a_leg * 2 * SECONDS_A_CALL
        bound = self.run.judge_shard_timeout_minutes * 60
        if seconds > bound:
            raise ValueError(
                f"pair_budget {knobs.pair_budget} over {knobs.shards} legs is {a_leg} pairs "
                f"a leg, which is {a_leg * 2} calls at {SECONDS_A_CALL} s, which is "
                f"{seconds:.0f} s against run.judge_shard_timeout_minutes of "
                f"{self.run.judge_shard_timeout_minutes} ({bound} s). Lower pair_budget, "
                "raise shards, or raise the timeout - which may not go past GitHub's 6 h "
                "job ceiling"
            )
        return self
