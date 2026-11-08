"""Which selected and observed model identities explain this run's results?"""

from summary_evaluator.hhem.contracts.service_settings import ServiceSettings
from summary_evaluator.serve_http.contracts.api_health import ApiHealth
from summary_evaluator.serve_http.contracts.api_settings import ApiComponent
from summary_evaluator.unieval.contracts.unieval_result import UnievalResult

from .contracts import PhaseEvidence as LegacyPhaseEvidence
from .phase_contracts import PhaseResult
from .report_contracts import PipelineResult
from .run_contracts import PreparedRun


def scorer_health(phase: PhaseResult | None, scorer: ApiComponent) -> ApiHealth | None:
    if isinstance(phase, LegacyPhaseEvidence):
        return phase.api_health
    return next(
        (api.health for api in phase.scorer_apis if api.scorer == scorer), None
    ) if phase is not None else None


def model_rows(evidence: PipelineResult, settings: ServiceSettings) -> list[tuple[object, ...]]:
    generation, phase = evidence.generation, evidence.evaluation_phase
    result = phase.evaluation if phase else None
    unieval = phase.unieval if phase else None
    selected = evidence.prepared.selected if evidence.prepared else None
    loaded = generation.loaded if generation else None
    hhem_health = scorer_health(phase, "hhem")
    unieval_health = scorer_health(phase, "unieval")
    hhem_model = (result.model if result else None) or (
        hhem_health.hhem.model if hhem_health else None
    )
    unieval_model = (unieval.model if unieval else None) or (
        unieval_health.unieval.model if unieval_health else None
    )
    controls = unieval.effective_settings if unieval else None
    work = unieval.work if unieval else None
    return [
        (
            "Summarizer declaration (relative to config/)",
            selected.models_file if selected else None,
        ),
        ("Declared summarizer", selected.model_id if selected else "Not selected"),
        ("Loaded summarizer", loaded.model_id if loaded else "Not loaded"),
        ("Native process ID (PID)", loaded.pid if loaded else None),
        ("Weight repository", selected.repo if selected else None),
        ("Weight revision", selected.revision if selected else None),
        ("Weight file", selected.filename if selected else None),
        ("Weight SHA-256 (content identity)", loaded.sha256 if loaded else None),
        (
            "Declaration SHA-256 (settings identity)",
            selected.declaration_sha256 if selected else None,
        ),
        ("Source SHA-256 (exact input)", generation.source_sha256 if generation else None),
        ("Answer SHA-256 (accepted summary)", generation.summary_sha256 if generation else None),
        (
            "Independent reference SHA-256 (captured before generation)",
            (evidence.prepared.reference_summary_sha256 or "Not supplied")
            if evidence.prepared else None,
        ),
        (
            "Relevance selection",
            ("Enabled" if evidence.prepared.evaluate_relevance else "Disabled")
            if isinstance(evidence.prepared, PreparedRun)
            else "Required (historical four-score evidence)" if evidence.prepared
            else "Not resolved",
        ),
        (
            "Relevance skip reason",
            unieval.relevance_skip_reason or "Not skipped"
            if isinstance(unieval, UnievalResult) and unieval.effective_settings is not None
            else "Not recorded",
        ),
        ("HHEM model", hhem_model.reference if hhem_model else "Not loaded"),
        ("HHEM loaded revision", hhem_model.loaded_revision if hhem_model else "Not loaded"),
        ("HHEM foundation", hhem_model.foundation_reference if hhem_model else "Not loaded"),
        (
            "HHEM foundation revision",
            hhem_model.foundation_revision if hhem_model else "Not loaded",
        ),
        (
            "HHEM runtime",
            (
                f"Python {hhem_model.runtime_versions.python}; "
                f"PyTorch {hhem_model.runtime_versions.pytorch}; "
                f"Transformers {hhem_model.runtime_versions.transformers}"
            )
            if hhem_model
            else "Not loaded",
        ),
        ("HHEM source window", f"{settings.scoring.chunk_words} words"),
        ("HHEM overlap", f"{settings.scoring.chunk_overlap_words} words"),
        ("UniEval model", unieval_model.reference if unieval_model else "Not loaded"),
        ("UniEval loaded revision", unieval_model.loaded_revision if unieval_model else None),
        ("UniEval tokenizer revision", unieval_model.tokenizer_revision if unieval_model else None),
        (
            "UniEval reference-code revision",
            unieval_model.reference_code_revision if unieval_model else None,
        ),
        (
            "UniEval runtime",
            (
                f"Python {unieval_model.runtime_versions.python}; "
                f"PyTorch {unieval_model.runtime_versions.pytorch}; "
                f"Transformers {unieval_model.runtime_versions.transformers}; "
                f"Tokenizers {unieval_model.runtime_versions.tokenizers}; "
                f"NLTK {unieval_model.runtime_versions.nltk}"
            )
            if unieval_model
            else "Not loaded",
        ),
        (
            "UniEval consistency mode",
            controls.consistency_source_mode if controls else "Not resolved",
        ),
        (
            "UniEval complete-prompt allowance (tokens)",
            controls.max_input_tokens if controls else None,
        ),
        (
            "UniEval effective source budget (tokens)",
            controls.source_budget_tokens if controls else None,
        ),
        ("UniEval source windows", len(work.source_spans) if work and work.source_spans else None),
        ("UniEval summary sentences", work.summary_sentences if work else None),
        ("UniEval source characters", work.source_characters if work else None),
        (
            "UniEval source spans (zero-based character offsets, end excluded)",
            "; ".join(f"[{span.start}, {span.end})" for span in work.source_spans)
            if work and work.source_spans
            else None,
        ),
    ]
