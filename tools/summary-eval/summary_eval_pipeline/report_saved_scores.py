"""Which native scores and explicit failures belong in the short Actions table?"""

from collections.abc import Sequence

from .contracts import PipelineError
from .saved_requests import SavedSummary


def describe_score(value: float | None) -> str:
    return "Not available" if value is None else str(value)


def render_saved_scores(
    summaries: Sequence[SavedSummary], errors: Sequence[PipelineError],
) -> str:
    lines = [
        "## Native summary evaluation",
        "",
        "### Saved summary scores",
        "",
    ]
    for index, summary in enumerate(summaries, 1):
        hhem, unieval = summary.outcomes.hhem, summary.outcomes.unieval
        scores = unieval.scores if unieval is not None else None
        consistency_mode = (
            f"`{unieval.effective_settings.consistency_source_mode}`"
            if unieval is not None and unieval.effective_settings is not None
            else "Not available"
        )
        lines.extend([
            f"#### Item {index}",
            "",
            f"**Table B{index} - HHEM**",
            "",
            "| Id | Metric | HHEM | Evaluator status |",
            "| --- | --- | --- | --- |",
            f"| B{index}.1 | Faithfulness | "
            f"{describe_score(hhem.hhem if hhem is not None else None)} | "
            f"{hhem.status if hhem is not None else 'not available'} |",
            "",
            f"**Table C{index} - UniEval**",
            "",
            "| Id | Metric | UniEval | Evaluator status | Consistency mode |",
            "| --- | --- | --- | --- | --- |",
        ])
        for row, dimension in enumerate(("fluency", "coherence", "consistency", "relevance"), 1):
            status = unieval.status if unieval is not None else "not available"
            if (
                dimension == "relevance"
                and unieval is not None
                and unieval.relevance_skip_reason is not None
            ):
                status = f"Skipped: {unieval.relevance_skip_reason}"
            lines.append(
                f"| C{index}.{row} | {dimension.capitalize()} | "
                f"{describe_score(getattr(scores, dimension) if scores is not None else None)} | "
                f"{status} | {consistency_mode if dimension == 'consistency' else '-'} |"
            )
        lines.append("")
    lines.append("")
    for index, summary in enumerate(summaries, 1):
        unieval = summary.outcomes.unieval
        if summary.outcomes.hhem is not None:
            for hhem_error in summary.outcomes.hhem.errors:
                lines.append(f"- Item {index} HHEM: `{hhem_error.code}`.")
        if unieval is not None:
            for unieval_error in unieval.errors:
                detail = ""
                if unieval_error.input_tokens is not None:
                    detail = (
                        f" ({unieval_error.input_tokens} assembled input tokens; "
                        f"configured allowance {unieval_error.allowed_tokens})"
                    )
                lines.append(f"- Item {index} UniEval: `{unieval_error.code}`{detail}.")
        for summary_error in summary.errors:
            lines.append(f"- Item {index} {summary_error.service}: `{summary_error.code}`.")
    for workflow_error in errors:
        cause = (
            f" / `{workflow_error.source_code}`"
            if workflow_error.source_code is not None else ""
        )
        lines.append(
            f"- {workflow_error.service} {workflow_error.phase}: `{workflow_error.code}`{cause}."
        )
    if not summaries:
        lines.append("No saved source/summary pair was accepted; neither evaluator was called.")
    return "\n".join(lines) + "\n"
