"""Which legacy coverage metrics follow the genuine ordered dimension calls and retrieval links?"""

from collections.abc import Callable
from typing import Any

from summary_evaluator.source_coverage.contracts.model_call import CoverageBackend
from summary_evaluator.source_coverage.contracts.scoring_warning import CoverageWarningCode
from summary_evaluator.source_coverage.contracts.service_settings import CoveragePreparation
from summary_evaluator.source_coverage.prepare_text import (
    chunk_document,
    extract_macro_skeleton,
    split_sentences,
)
from summary_evaluator.source_coverage.retrieve_evidence import EvidenceRetriever
from summary_evaluator.source_coverage.validate_model_output import validate_model_output

# These evidence phrases retain the existing metric's explanation format.
UNSUPPORTED_EVIDENCE = "[No strongly entailed passage in matched section]"
SUPPORTED_REASON = "Supported by source evidence."


def score_coverage(
    source_text: str,
    summary_text: str,
    settings: CoveragePreparation,
    backend: CoverageBackend,
    warning: Callable[[CoverageWarningCode], None] | None = None,
) -> dict[str, Any]:
    clean_summary = summary_text.strip() or settings.empty_summary
    clean_source = source_text.strip() or settings.empty_source
    data_fluency = backend.convert_input(output_list=[clean_summary])
    eval_fluency = validate_model_output(
        backend.evaluate_dimension(data_fluency, "fluency"), len(data_fluency), "fluency"
    )
    fluency = round(eval_fluency[0]["fluency"], settings.score_decimals)

    macro = extract_macro_skeleton(clean_source, settings)
    data_coherence = backend.convert_input(output_list=[clean_summary], src_list=[macro])
    eval_coherence = validate_model_output(
        backend.evaluate_dimension(data_coherence, "coherence"), len(data_coherence), "coherence"
    )
    coherence = round(eval_coherence[0]["coherence"], settings.score_decimals)
    chunks = chunk_document(clean_source, settings)
    sentences = split_sentences(clean_summary, settings, warning)
    retriever = EvidenceRetriever(chunks, settings, warning)

    unique_pairs: dict[tuple[str, str], float] = {}
    pair_mappings: list[tuple[int, int, str, str]] = []
    for sentence_index, sentence in enumerate(sentences):
        for chunk_index, chunk in retriever.retrieve_top_k(sentence):
            pair_key = (chunk, sentence)
            if pair_key not in unique_pairs:
                unique_pairs[pair_key] = 0.0
            pair_mappings.append((sentence_index, chunk_index, chunk, sentence))

    sentence_details: list[dict[str, Any]] = []
    supported_chunks = set()
    chunk_max_scores: dict[int, float] = dict.fromkeys(range(len(chunks)), 0.0)
    threshold = f"{settings.grounding_threshold:.{settings.threshold_decimals}f}"
    if unique_pairs:
        eval_source = [key[0] for key in unique_pairs]
        eval_output = [key[1] for key in unique_pairs]
        data_consistency = backend.convert_input(output_list=eval_output, src_list=eval_source)
        consistency_results = validate_model_output(
            backend.evaluate_dimension(data_consistency, "consistency"),
            len(data_consistency),
            "consistency",
        )
        for index, result in enumerate(consistency_results):
            pair_key = (eval_source[index], eval_output[index])
            unique_pairs[pair_key] = float(result["consistency"])

        sentence_scores: dict[int, float] = {}
        sentence_chunk_map: dict[int, int] = {}
        for sentence_index, chunk_index, chunk, sentence in pair_mappings:
            score = unique_pairs[(chunk, sentence)]
            if score > chunk_max_scores[chunk_index]:
                chunk_max_scores[chunk_index] = score
            if sentence_index not in sentence_scores or score > sentence_scores[sentence_index]:
                sentence_scores[sentence_index] = score
                sentence_chunk_map[sentence_index] = chunk_index

        for sentence_index, sentence in enumerate(sentences):
            score = round(sentence_scores[sentence_index], settings.score_decimals)
            chunk_index = sentence_chunk_map[sentence_index]
            supported = score >= settings.grounding_threshold
            if supported:
                supported_chunks.add(chunk_index)
            matched_chunk = chunks[chunk_index] if chunk_index < len(chunks) else clean_source
            if supported:
                source_sentence = retriever.find_best_sentence(sentence, matched_chunk)
                reason = SUPPORTED_REASON
            else:
                source_sentence = UNSUPPORTED_EVIDENCE
                reason = (
                    f"Chunk entailment score ({score:.{settings.score_decimals}f}) "
                    f"fell below the {threshold} threshold."
                )
            sentence_details.append(
                {
                    "sentence_index": sentence_index + 1,
                    "text": sentence,
                    "score": score,
                    "matched_chunk": chunk_index + 1,
                    "supported": supported,
                    "source_sentence": source_sentence.strip(),
                    "reason": reason,
                }
            )

    uncovered_sections: list[dict[str, Any]] = []
    for chunk_index in range(len(chunks)):
        if chunk_index not in supported_chunks:
            words = chunks[chunk_index].strip().split()
            excerpt = " ".join(words[: settings.uncovered_excerpt_words]) + (
                "..." if len(words) > settings.uncovered_excerpt_words else ""
            )
            maximum = round(chunk_max_scores.get(chunk_index, 0.0), settings.score_decimals)
            uncovered_sections.append(
                {
                    "chunk_index": chunk_index + 1,
                    "chunk_total": len(chunks),
                    "excerpt": excerpt,
                    "max_similarity_score": maximum,
                    "reason": (
                        f"No summary claim reached the {threshold} grounding threshold "
                        f"for this section (Peak entailment: {maximum}). "
                        "Key facts from this section were omitted."
                    ),
                }
            )
    consistency = (
        round(
            sum(sentence["score"] for sentence in sentence_details) / len(sentence_details),
            settings.score_decimals,
        )
        if sentence_details
        else 0.0
    )
    total_chunks = len(chunks) if chunks else 1
    return {
        "overall_consistency": consistency,
        "coherence": coherence,
        "fluency": fluency,
        "document_chunks_total": len(chunks),
        "document_chunks_covered": len(supported_chunks),
        "chunk_coverage_percent": round(
            len(supported_chunks) / total_chunks * 100, settings.coverage_decimals
        ),
        "sentence_breakdown": sentence_details,
        "uncovered_sections": uncovered_sections,
    }
