#!/usr/bin/env python3
"""
.github/scripts/serve-evaluator.py
Verb-Noun: Serves the UniEval quality evaluation microservice over FastAPI.
Outputs structured JSONL to stdout, appends evaluation events to eval-events.jsonl,
and implements deterministic RFC 4122 UUIDv5 hashing.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import importlib.util
import json
import logging
import os
from pathlib import Path
import re
import sys
import time
from typing import Any
import uuid

# -------------------------------------------------------------
# 0. IN-MEMORY SHIM FOR PRETTYTABLE (IF MISSING)
# -------------------------------------------------------------
if importlib.util.find_spec("prettytable") is None:
    import types

    dummy = types.ModuleType("prettytable")

    class DummyPrettyTable:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.field_names: list[str] = []
            self.rows: list[Any] = []

        def add_row(self, row: Any) -> None:
            self.rows.append(row)

        def get_string(self) -> str:
            return ""

    dummy.PrettyTable = DummyPrettyTable
    sys.modules["prettytable"] = dummy

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
import torch
import uvicorn

# -------------------------------------------------------------
# 1. STRUCTURED JSONL LOGGING
# -------------------------------------------------------------
EVAL_EVENTS_PATH = Path(os.getenv("EVAL_EVENTS_PATH", "eval-events.jsonl"))
UUIDV5_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", 
    "aren't", "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", 
    "but", "by", "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't", 
    "doing", "don't", "down", "during", "each", "few", "for", "from", "further", "had", "hadn't", 
    "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here", 
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", 
    "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself", "let's", "me", 
    "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", 
    "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same", 
    "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such", 
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then", "there", 
    "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this", "those", 
    "through", "to", "too", "under", "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", 
    "we're", "we've", "were", "weren't", "what", "what's", "when", "when's", "where", "where's", 
    "which", "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would", "wouldn't", 
    "you", "you'd", "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves"
}


def log_structured(level: str, message: str, **kwargs: Any) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level.upper(),
        "service": "unieval-evaluator",
        "message": message,
        **kwargs,
    }
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def generate_deterministic_event_id(
    runner_name: str, shard_id: str, source_url: str, event_type: str
) -> str:
    seed = f"runner:{runner_name}:shard:{shard_id}:source:{source_url}:event:{event_type}"
    return f"evt-{uuid.uuid5(UUIDV5_NAMESPACE, seed)}"


def append_eval_event(event_dict: dict[str, Any]) -> None:
    try:
        with EVAL_EVENTS_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event_dict) + "\n")
    except Exception as e:
        log_structured("ERROR", "Failed to write event to eval-events.jsonl", error=str(e))


class JsonlUvicornFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": "uvicorn-server",
            "message": record.getMessage(),
        }
        return json.dumps(data)


# -------------------------------------------------------------
# 2. IN-FLIGHT HARDWARE SAMPLER
# -------------------------------------------------------------
class HardwareSampler:
    @staticmethod
    def read_cpu_stat() -> tuple[int, int]:
        try:
            with Path("/proc/stat").open() as f:
                line = f.readline()
            parts = [int(p) for p in line.split()[1:]]
            idle = parts[3] + parts[4]
            total = sum(parts[:7])
            return total, idle
        except Exception:
            return 0, 0

    @staticmethod
    def get_memory_snapshot() -> dict[str, int]:
        rss_kb = 0
        swap_kb = 0
        try:
            with Path("/proc/self/status").open() as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        rss_kb = int(line.split()[1])
                    if line.startswith("VmSwap:"):
                        swap_kb = int(line.split()[1])
        except Exception:
            pass
        return {
            "server_vm_rss_mb": round(rss_kb / 1024),
            "server_vm_swap_mb": round(swap_kb / 1024),
        }


# -------------------------------------------------------------
# 3. TEXT CHUNKING & EVIDENCE RETRIEVAL
# -------------------------------------------------------------
def split_sentences(text: str) -> list[str]:
    try:
        from nltk.tokenize import sent_tokenize
        sentences = sent_tokenize(text)
    except Exception:
        sentences = re.split(r"(?<=[.!?])\s+", text)
    valid = [s.strip() for s in sentences if len(s.strip()) > 10]
    return valid if valid else ([text.strip()] if text.strip() else ["Summary content sentence."])


def chunk_document(
    text: str, chunk_words: int = 380, stride_words: int = 80
) -> list[str]:
    words = text.split()
    if len(words) <= chunk_words:
        return [text] if text.strip() else ["Empty document content."]

    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_words])
        chunks.append(chunk)
        if i + chunk_words >= len(words):
            break
        i += chunk_words - stride_words
    return chunks if chunks else ["Empty document content."]


def extract_macro_skeleton(text: str, max_words: int = 380) -> str:
    paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 40]
    if not paragraphs:
        return text[:1500] if text else "Document body."
    if len(paragraphs) <= 3:
        return "\n\n".join(paragraphs)[:1800]
    lead = paragraphs[0] + "\n\n" + paragraphs[1]
    tail = paragraphs[-1]
    combined = lead + "\n\n[...]\n\n" + tail
    words = combined.split()
    return " ".join(words[:max_words]) if len(words) > max_words else combined


def get_content_words(text: str) -> set[str]:
    tokens = re.findall(r"\w+", text.lower())
    return {t for t in tokens if t not in STOPWORDS and len(t) > 2}


class EvidenceRetriever:
    def __init__(self, chunks: list[str]):
        self.chunks = chunks
        self.use_bm25 = False
        try:
            from rank_bm25 import BM25Okapi

            tokenized = [
                [tok for tok in re.findall(r"\w+", c.lower()) if tok not in STOPWORDS]
                for c in self.chunks
            ]
            tokenized = [tok if tok else ["document"] for tok in tokenized]
            self.bm25 = BM25Okapi(tokenized)
            self.use_bm25 = True
        except Exception:
            self.use_bm25 = False

    def retrieve_top_k(self, sentence: str, k: int = 4) -> list[tuple[int, str]]:
        if len(self.chunks) <= k:
            return list(enumerate(self.chunks))
        tokens = [tok for tok in re.findall(r"\w+", sentence.lower()) if tok not in STOPWORDS]
        if not tokens:
            tokens = ["text"]

        if self.use_bm25:
            try:
                scores = self.bm25.get_scores(tokens)
                top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
            except Exception:
                top_idx = list(range(min(k, len(self.chunks))))
        else:
            token_set = set(tokens)
            scores = [
                len(token_set.intersection(get_content_words(c)))
                for c in self.chunks
            ]
            top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [(idx, self.chunks[idx]) for idx in top_idx]


# -------------------------------------------------------------
# 4. FASTAPI SERVICE LIFECYCLE
# -------------------------------------------------------------
EVALUATOR_INSTANCE = None
UNIEVAL_MODULES: dict[str, Any] = {}
CONCURRENCY_SEMAPHORE: asyncio.Semaphore | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global EVALUATOR_INSTANCE, UNIEVAL_MODULES, CONCURRENCY_SEMAPHORE
    CONCURRENCY_SEMAPHORE = asyncio.Semaphore(1)

    unieval_dir = os.getenv("UNIEVAL_DIR", "/tmp/unieval")
    if unieval_dir not in sys.path:
        sys.path.insert(0, unieval_dir)

    try:
        from metric.evaluator import get_evaluator
        from utils import convert_to_json

        UNIEVAL_MODULES["get_evaluator"] = get_evaluator
        UNIEVAL_MODULES["convert_to_json"] = convert_to_json
    except ImportError as e:
        log_structured("ERROR", f"Failed to load UniEval from {unieval_dir}", error=str(e))
        raise e

    cores = os.cpu_count() or 2
    torch.set_num_threads(cores)

    log_structured("INFO", f"Initializing UniEval (T5-Large) with {cores} threads on device='cpu'")
    EVALUATOR_INSTANCE = get_evaluator("summarization", max_length=1024, device="cpu")
    log_structured("INFO", "UniEval service warmed and listening on port 9933")
    yield
    log_structured("INFO", "Shutting down UniEval service")


app = FastAPI(title="UniEval Quality Microservice", lifespan=lifespan)


@app.middleware("http")
async def jsonl_logging_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    log_structured(
        "INFO",
        f"HTTP {request.method} {request.url.path} Completed",
        status_code=response.status_code,
        duration_ms=duration_ms,
        client=request.client.host if request.client else "unknown",
    )
    return response


class EvaluationRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    correlation_id: str = Field(..., alias="correlationId")
    runner_name: str = Field(..., alias="runnerName")
    shard_id: str = Field(..., alias="shardId")
    source_identifier: str = Field(..., alias="sourceIdentifier")
    source_title: str = Field(..., alias="sourceTitle")
    source_text: str = Field(..., alias="sourceText")
    summary_text: str = Field(..., alias="summaryText")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "evaluator_loaded": EVALUATOR_INSTANCE is not None,
        "memory": HardwareSampler.get_memory_snapshot(),
    }


def compute_unieval_sync(source_text: str, summary_text: str) -> dict[str, Any]:
    convert_to_json = UNIEVAL_MODULES["convert_to_json"]
    evaluator = EVALUATOR_INSTANCE

    # Execute all forward evaluations within torch.inference_mode (eliminates autograd overhead)
    with torch.inference_mode():
        # 1. Fluency
        data_flu = convert_to_json(output_list=[summary_text])
        eval_flu = evaluator.evaluate(data_flu, dims=["fluency"], overall=False, batch_size=16)
        fluency = round(eval_flu[0]["fluency"], 3) if eval_flu else 0.0

        # 2. Coherence
        macro_ctx = extract_macro_skeleton(source_text, max_words=380)
        data_coh = convert_to_json(output_list=[summary_text], src_list=[macro_ctx])
        eval_coh = evaluator.evaluate(data_coh, dims=["coherence"], overall=False, batch_size=16)
        coherence = round(eval_coh[0]["coherence"], 3) if eval_coh else 0.0

        # 3. Chunked Sentence-Level Consistency with Expanded Candidate Context (k=4)
        chunks = chunk_document(source_text, chunk_words=380, stride_words=80)
        sentences = split_sentences(summary_text)

        retriever = EvidenceRetriever(chunks)
        
        # Deduplicate identical (chunk, sentence) pairs before model execution
        unique_pairs: dict[tuple[str, str], float] = {}
        pair_mappings: list[tuple[int, int, str, str]] = []

        for s_idx, sentence in enumerate(sentences):
            for c_idx, chunk in retriever.retrieve_top_k(sentence, k=4):
                pair_key = (chunk, sentence)
                if pair_key not in unique_pairs:
                    unique_pairs[pair_key] = 0.0
                pair_mappings.append((s_idx, c_idx, chunk, sentence))

        sentence_details = []
        supported_chunks = set()
        chunk_max_scores: dict[int, float] = {i: 0.0 for i in range(len(chunks))}

        if unique_pairs:
            eval_src = [k[0] for k in unique_pairs.keys()]
            eval_out = [k[1] for k in unique_pairs.keys()]

            data_cons = convert_to_json(output_list=eval_out, src_list=eval_src)
            cons_res = evaluator.evaluate(data_cons, dims=["consistency"], overall=False, batch_size=16)

            for idx, r in enumerate(cons_res):
                pair_key = (eval_src[idx], eval_out[idx])
                unique_pairs[pair_key] = float(r.get("consistency", 0.0))

            sentence_scores: dict[int, float] = {}
            sentence_chunk_map: dict[int, int] = {}

            for s_idx, c_idx, chunk, sentence in pair_mappings:
                sc = unique_pairs.get((chunk, sentence), 0.0)
                if sc > chunk_max_scores[c_idx]:
                    chunk_max_scores[c_idx] = sc
                if s_idx not in sentence_scores or sc > sentence_scores[s_idx]:
                    sentence_scores[s_idx] = sc
                    sentence_chunk_map[s_idx] = c_idx

            for s_idx, sentence in enumerate(sentences):
                sc = round(sentence_scores.get(s_idx, 0.0), 3)
                c_idx = sentence_chunk_map.get(s_idx, 0)
                supported = sc >= 0.50
                if supported:
                    supported_chunks.add(c_idx)

                matched_chunk_text = chunks[c_idx] if c_idx < len(chunks) else source_text
                chunk_sentences = split_sentences(matched_chunk_text)
                summary_content_words = get_content_words(sentence)

                best_source_sent = ""
                best_overlap_count = 0

                for cs in chunk_sentences:
                    cs_content_words = get_content_words(cs)
                    overlap = len(summary_content_words.intersection(cs_content_words))
                    if overlap > best_overlap_count:
                        best_overlap_count = overlap
                        best_source_sent = cs

                # If no meaningful content words align within the chunk, search across all source chunks
                if best_overlap_count == 0:
                    for fallback_chunk in chunks:
                        for cs in split_sentences(fallback_chunk):
                            cs_words = get_content_words(cs)
                            overlap = len(summary_content_words.intersection(cs_words))
                            if overlap > best_overlap_count:
                                best_overlap_count = overlap
                                best_source_sent = cs

                # If still zero lexical or entity overlap exists, explicitly mark as ungrounded
                if best_overlap_count == 0 or not best_source_sent:
                    source_attribution = "[No corresponding passage found in source document (potential ungrounded claim)]"
                    diagnostic_reason = (
                        f"Zero content-word alignment with source document. Chunk entailment score was {sc:.3f} (< 0.50)."
                    )
                else:
                    source_attribution = best_source_sent.strip()
                    diagnostic_reason = (
                        "Supported by source evidence."
                        if supported
                        else f"Consistency entailment score ({sc:.3f}) fell below the 0.50 threshold against chunk {c_idx + 1}."
                    )

                sentence_details.append(
                    {
                        "sentence_index": s_idx + 1,
                        "text": sentence,
                        "score": sc,
                        "matched_chunk": c_idx + 1,
                        "supported": supported,
                        "source_sentence": source_attribution,
                        "reason": diagnostic_reason,
                    }
                )

        uncovered_sections = []
        for c_idx in range(len(chunks)):
            if c_idx not in supported_chunks:
                chunk_text = chunks[c_idx].strip()
                words = chunk_text.split()
                lead_snippet = " ".join(words[:35]) + ("..." if len(words) > 35 else "")
                max_sc = round(chunk_max_scores.get(c_idx, 0.0), 3)
                uncovered_sections.append(
                    {
                        "chunk_index": c_idx + 1,
                        "chunk_total": len(chunks),
                        "excerpt": lead_snippet,
                        "max_similarity_score": max_sc,
                        "reason": (
                            f"No summary claim reached the 0.50 grounding threshold for this section "
                            f"(Peak entailment: {max_sc}). Key facts from this section were omitted."
                        ),
                    }
                )

        avg_consistency = (
            round(sum(s["score"] for s in sentence_details) / len(sentence_details), 3)
            if sentence_details
            else 0.0
        )
        total_chunks = len(chunks) if chunks else 1
        coverage_pct = round((len(supported_chunks) / total_chunks) * 100, 1)

        return {
            "overall_consistency": avg_consistency,
            "coherence": coherence,
            "fluency": fluency,
            "document_chunks_total": len(chunks),
            "document_chunks_covered": len(supported_chunks),
            "chunk_coverage_percent": coverage_pct,
            "sentence_breakdown": sentence_details,
            "uncovered_sections": uncovered_sections,
        }


@app.post("/v1/evaluate")
async def evaluate_article(req: EvaluationRequest):
    if not EVALUATOR_INSTANCE:
        raise HTTPException(status_code=503, detail="Evaluator not loaded")

    t_start = time.perf_counter()
    stat_start_total, stat_start_idle = HardwareSampler.read_cpu_stat()

    sem = CONCURRENCY_SEMAPHORE or asyncio.Semaphore(1)
    async with sem:
        metrics = await asyncio.to_thread(
            compute_unieval_sync, req.source_text, req.summary_text
        )

    duration_ms = round((time.perf_counter() - t_start) * 1000)
    stat_end_total, stat_end_idle = HardwareSampler.read_cpu_stat()
    delta_total = stat_end_total - stat_start_total
    delta_idle = stat_end_idle - stat_start_idle
    cpu_pct = (
        round(((delta_total - delta_idle) / delta_total) * 100, 1)
        if delta_total > 0
        else 0.0
    )
    mem_snap = HardwareSampler.get_memory_snapshot()

    event_id = generate_deterministic_event_id(
        req.runner_name,
        req.shard_id,
        req.source_identifier,
        "QUALITY_EVALUATION_COMPLETED",
    )

    event_payload = {
        "eventId": event_id,
        "eventType": "QUALITY_EVALUATION_COMPLETED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "correlationId": req.correlation_id,
        "durationMs": duration_ms,
        "cumulativeMs": 0,
        "payload": {
            "sourceIdentifier": req.source_identifier,
            "sourceTitle": req.source_title,
            "metrics": metrics,
            "serverTelemetry": {
                "duration_ms": duration_ms,
                "cpu_percent": cpu_pct,
                "server_vm_rss_mb": mem_snap["server_vm_rss_mb"],
                "server_vm_swap_mb": mem_snap["server_vm_swap_mb"],
            },
        },
    }

    append_eval_event(event_payload)

    log_structured(
        "INFO",
        "Evaluation completed successfully",
        eventId=event_id,
        correlationId=req.correlation_id,
        sourceIdentifier=req.source_identifier,
        durationMs=duration_ms,
        consistency=metrics["overall_consistency"],
        coveragePct=metrics["chunk_coverage_percent"],
    )

    return {"status": "success", "event": event_payload, "metrics": metrics}


if __name__ == "__main__":
    uvicorn_logger = logging.getLogger("uvicorn.access")
    uvicorn_logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonlUvicornFormatter())
    uvicorn_logger.addHandler(handler)

    uvicorn.run(app, host="127.0.0.1", port=9933, log_config=None, access_log=False)
