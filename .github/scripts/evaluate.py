#!/usr/bin/env python3
"""
.github/scripts/evaluate.py
Evaluates summarization quality across Consistency, Discourse Coherence, and Fluency
using the UniEval benchmark (MingZhong/unieval-sum on T5-large) via chunked BM25 retrieval.

Standard:
- Explicit CPU binding: device='cpu' to prevent CUDA crashes on standard runners.
- Chunked windowing: Overcoming T5's 512/1024 token limit on 6,000-word texts.
- Zero extra LLM tokens: Reference-free sentence consistency and sectional coverage.
- Full parity with ai-pipeline.ts JSONL event stream and GitHub Step Summary.
"""

import argparse
import json
import os
import re
import sys
from typing import Dict, List, Tuple

import torch


# -------------------------------------------------------------
# 1. TEXT CHUNKING & PRE-PROCESSING
# -------------------------------------------------------------
def split_sentences(text: str) -> List[str]:
    """Splits prose into distinct sentences using NLTK or regex fallback."""
    try:
        from nltk.tokenize import sent_tokenize

        sentences = sent_tokenize(text)
    except Exception:
        sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if len(s.strip()) > 10]


def chunk_document(
    text: str, chunk_words: int = 380, stride_words: int = 80
) -> List[str]:
    """Divides long texts (up to 6,000+ words) into overlapping semantic windows."""
    words = text.split()
    if len(words) <= chunk_words:
        return [text]

    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_words])
        chunks.append(chunk)
        if i + chunk_words >= len(words):
            break
        i += chunk_words - stride_words
    return chunks


def extract_macro_skeleton(text: str, max_words: int = 380) -> str:
    """Extracts structural lead and tail paragraphs to evaluate macro document discourse coherence."""
    paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 40]
    if not paragraphs:
        return text[:1500]

    if len(paragraphs) <= 3:
        return "\n\n".join(paragraphs)[:1800]

    lead = paragraphs[0] + "\n\n" + paragraphs[1]
    tail = paragraphs[-1]
    combined = lead + "\n\n[...]\n\n" + tail
    words = combined.split()
    if len(words) > max_words:
        return " ".join(words[:max_words])
    return combined


# -------------------------------------------------------------
# 2. FAST BM25 EVIDENCE RETRIEVAL
# -------------------------------------------------------------
class EvidenceRetriever:
    """Retrieves top-K candidate evidence chunks for a given summary sentence."""

    def __init__(self, chunks: List[str]):
        self.chunks = chunks
        self.use_bm25 = False
        try:
            from rank_bm25 import BM25Okapi

            tokenized_corpus = [
                re.findall(r"\w+", c.lower()) for c in self.chunks
            ]
            self.bm25 = BM25Okapi(tokenized_corpus)
            self.use_bm25 = True
        except ImportError:
            pass

    def retrieve_top_k(self, sentence: str, k: int = 2) -> List[Tuple[int, str]]:
        if len(self.chunks) <= k:
            return list(enumerate(self.chunks))

        query_tokens = re.findall(r"\w+", sentence.lower())
        if self.use_bm25:
            scores = self.bm25.get_scores(query_tokens)
            top_indices = sorted(
                range(len(scores)), key=lambda i: scores[i], reverse=True
            )[:k]
        else:
            query_set = set(query_tokens)
            scores = [
                len(query_set.intersection(set(re.findall(r"\w+", c.lower()))))
                for c in self.chunks
            ]
            top_indices = sorted(
                range(len(scores)), key=lambda i: scores[i], reverse=True
            )[:k]

        return [(idx, self.chunks[idx]) for idx in top_indices]


# -------------------------------------------------------------
# 3. UNIEVAL EVALUATION HARNESS
# -------------------------------------------------------------
def run_evaluation(
    source_text: str, summary_text: str, unieval_dir: str
) -> Dict:
    sys.path.insert(0, unieval_dir)
    try:
        from metric.evaluator import get_evaluator
        from utils import convert_to_json
    except ImportError as e:
        raise RuntimeError(
            f"Failed to import UniEval modules from {unieval_dir}: {e}"
        )

    # Allocate all available CPU cores for PyTorch
    torch.set_num_threads(os.cpu_count() or 2)

    print(
        "[EVALUATOR] 🤖 Initializing UniEval (MingZhong/unieval-sum) on device='cpu'..."
    )
    # Explicitly pass device='cpu' to prevent default CUDA assertion failure on GitHub Actions
    evaluator = get_evaluator("summarization", max_length=1024, device="cpu")

    # 1. Fluency (Summary only, reference-free)
    print("[EVALUATOR] 🔬 Calculating Fluency score...")
    data_flu = convert_to_json(output_list=[summary_text])
    eval_flu = evaluator.evaluate(data_flu, dims=["fluency"], overall=False)
    fluency_score = round(eval_flu[0]["fluency"], 3)

    # 2. Coherence against Macro Structural Skeleton
    print("[EVALUATOR] 🔬 Calculating Coherence against macro structure...")
    macro_context = extract_macro_skeleton(source_text, max_words=380)
    data_coh = convert_to_json(
        output_list=[summary_text], src_list=[macro_context]
    )
    eval_coh = evaluator.evaluate(data_coh, dims=["coherence"], overall=False)
    coherence_score = round(eval_coh[0]["coherence"], 3)

    # 3. Chunked Sentence-Level Consistency (Grounding)
    print(
        "[EVALUATOR] 🔬 Calculating Chunked Sentence Grounding (Consistency)..."
    )
    chunks = chunk_document(source_text, chunk_words=380, stride_words=80)
    sentences = split_sentences(summary_text)

    if not sentences:
        sentences = [summary_text]

    retriever = EvidenceRetriever(chunks)
    eval_pairs_src = []
    eval_pairs_out = []
    pair_meta = []

    for s_idx, sentence in enumerate(sentences):
        top_candidates = retriever.retrieve_top_k(sentence, k=2)
        for c_idx, chunk in top_candidates:
            eval_pairs_src.append(chunk)
            eval_pairs_out.append(sentence)
            pair_meta.append((s_idx, c_idx))

    data_cons = convert_to_json(
        output_list=eval_pairs_out, src_list=eval_pairs_src
    )
    cons_results = evaluator.evaluate(
        data_cons, dims=["consistency"], overall=False
    )

    sentence_scores: Dict[int, float] = {}
    sentence_chunk_map: Dict[int, int] = {}

    for idx, res in enumerate(cons_results):
        s_idx, c_idx = pair_meta[idx]
        score = res["consistency"]
        if (
            s_idx not in sentence_scores
            or score > sentence_scores[s_idx]
        ):
            sentence_scores[s_idx] = score
            sentence_chunk_map[s_idx] = c_idx

    sentence_details = []
    supported_chunks = set()
    for s_idx, sentence in enumerate(sentences):
        score = round(sentence_scores.get(s_idx, 0.0), 3)
        c_idx = sentence_chunk_map.get(s_idx, 0)
        is_supported = score >= 0.50
        if is_supported:
            supported_chunks.add(c_idx)

        sentence_details.append(
            {
                "sentence_index": s_idx + 1,
                "text": sentence,
                "score": score,
                "matched_chunk": c_idx + 1,
                "supported": is_supported,
            }
        )

    avg_consistency = (
        round(sum(s["score"] for s in sentence_details) / len(sentence_details), 3)
        if sentence_details
        else 0.0
    )
    chunk_coverage_pct = round((len(supported_chunks) / len(chunks)) * 100, 1)

    return {
        "overall_consistency": avg_consistency,
        "coherence": coherence_score,
        "fluency": fluency_score,
        "document_chunks_total": len(chunks),
        "document_chunks_covered": len(supported_chunks),
        "chunk_coverage_percent": chunk_coverage_pct,
        "sentence_breakdown": sentence_details,
    }


# -------------------------------------------------------------
# 4. STEP SUMMARY & JSONL AUDIT
# -------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Run UniEval summarization audit"
    )
    parser.add_argument(
        "--input-events",
        default="pipeline-events.jsonl",
        help="Path to pipeline events file",
    )
    parser.add_argument(
        "--unieval-dir",
        default="/tmp/unieval",
        help="Path to cloned UniEval repository",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input_events):
        print(f"❌ Input events file {args.input_events} does not exist.")
        sys.exit(1)

    structured_outputs = []
    with open(args.input_events, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                if event.get("eventType") == "OUTPUT_STRUCTURED":
                    structured_outputs.append(event)
            except Exception:
                continue

    if not structured_outputs:
        print("⚠️ No OUTPUT_STRUCTURED events found to evaluate.")
        sys.exit(0)

    summary_file = os.getenv("GITHUB_STEP_SUMMARY")
    summary_lines = [
        "## 🧪 Summarization Quality Audit (UniEval Suite)",
        "",
        "> Quality and factual grounding evaluated using `MingZhong/unieval-sum` (T5-Large) via chunked BM25 retrieval.",
        "",
    ]

    for idx, item in enumerate(structured_outputs):
        payload = item["payload"]
        source_text = payload["source_audit"]["extractedText"]
        summary_text = payload.get(
            "analytic_synthesis"
        ) or payload.get("executive_summary", "")
        headline = payload.get("headline", "Article")

        print(
            f"\n[EVALUATOR] 🚀 Evaluating Target ({idx + 1}/{len(structured_outputs)}): '{headline}'..."
        )
        metrics = run_evaluation(source_text, summary_text, args.unieval_dir)

        print(
            f"::notice title=UniEval Quality Verified::Consistency: {metrics['overall_consistency']} | "
            f"Coverage: {metrics['chunk_coverage_percent']}% | Coherence: {metrics['coherence']} | Fluency: {metrics['fluency']}"
        )

        unsupported = [
            s for s in metrics["sentence_breakdown"] if not s["supported"]
        ]
        if unsupported:
            print(
                f"::warning title=Ungrounded Content Detected::{len(unsupported)} of {len(metrics['sentence_breakdown'])} "
                f"sentences scored < 0.50 consistency against source chunks."
            )

        consistency_rating = (
            "🟢 Fully Supported"
            if metrics["overall_consistency"] >= 0.75
            else "⚠️ Grounding Variance"
        )
        coverage_rating = (
            "🟢 High Coverage"
            if metrics["chunk_coverage_percent"] >= 60.0
            else "⚠️ Partial Coverage"
        )
        coherence_rating = (
            "🟢 Fluid"
            if metrics["coherence"] >= 0.70
            else "⚠️ Fragmented"
        )
        fluency_rating = (
            "🟢 Natural"
            if metrics["fluency"] >= 0.85
            else "⚠️ Mechanical"
        )

        summary_lines.extend(
            [
                f"### Target {idx + 1}: *\"{headline}\"*",
                "",
                "| Evaluation Dimension | Metric Score | Operational Rating | Evaluation Methodology |",
                "| :--- | :---: | :---: | :--- |",
                f"| **Consistency (Factuality)** | **`{metrics['overall_consistency']}`** | {consistency_rating} | Chunked BM25 Sentence Entailment |",
                f"| **Sectional Coverage** | **`{metrics['chunk_coverage_percent']}%`** | {coverage_rating} | {metrics['document_chunks_covered']} of {metrics['document_chunks_total']} document chunks represented |",
                f"| **Discourse Coherence** | **`{metrics['coherence']}`** | {coherence_rating} | Inter-sentence discourse flow against macro skeleton |",
                f"| **Fluency (Syntax)** | **`{metrics['fluency']}`** | {fluency_rating} | Grammatical well-formedness & readability |",
                "",
                "<details>",
                f"<summary><b>Inspect Sentence-by-Sentence Grounding Matrix ({len(metrics['sentence_breakdown'])} Sentences)</b></summary>",
                "",
                "| # | Summary Sentence | Matched Chunk | Consistency Score | Status |",
                "| :- | :--- | :-: | :-: | :-: |",
            ]
        )

        for s in metrics["sentence_breakdown"]:
            status = "✅ Supported" if s["supported"] else "❌ Unsupported"
            summary_lines.append(
                f"| {s['sentence_index']} | {s['text']} | Chunk {s['matched_chunk']} | `{s['score']}` | {status} |"
            )

        summary_lines.extend(["", "</details>", "", "---", ""])

        # Write audit event to JSONL
        eval_event = {
            "eventId": f"eval-{payload.get('source_audit', {}).get('sourceIdentifier', idx)}",
            "eventType": "QUALITY_EVALUATION_COMPLETED",
            "timestamp": payload.get("source_audit", {}).get("sourceTitle", ""),
            "payload": {
                "headline": headline,
                "sourceIdentifier": payload["source_audit"]["sourceIdentifier"],
                "metrics": metrics,
            },
        }
        with open(args.input_events, "a", encoding="utf-8") as f:
            f.write(json.dumps(eval_event) + "\n")

    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write("\n".join(summary_lines) + "\n")

    print("[EVALUATOR] ✅ Evaluation completed successfully.")


if __name__ == "__main__":
    main()
