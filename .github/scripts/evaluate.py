#!/usr/bin/env python3
"""
.github/scripts/evaluate.py
FastAPI microservice hosting UniEval (MingZhong/unieval-sum on T5-large).
Runs in Phase 2 with full system RAM (15 GB) to evaluate articles in parallel.
Instruments in-flight CPU/RAM consumption and emits RFC 4122 UUIDv5 events.
"""

import asyncio
import importlib.util
from contextlib import asynccontextmanager
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

from pydantic import BaseModel, ConfigDict, Field
import torch
import uvicorn
from fastapi import FastAPI, HTTPException

# -------------------------------------------------------------
# 1. CONSTANTS & RFC 4122 UUIDv5 GENERATOR
# -------------------------------------------------------------
UUIDV5_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def generate_event_id(
    runner_name: str, shard_id: str, epoch_ms: int, event_type: str
) -> str:
    seed = f"runner:{runner_name}:shard:{shard_id}:epoch:{epoch_ms}:event:{event_type}"
    return f"evt-{uuid.uuid5(UUIDV5_NAMESPACE, seed)}"


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
    return [s.strip() for s in sentences if len(s.strip()) > 10]


def chunk_document(
    text: str, chunk_words: int = 380, stride_words: int = 80
) -> list[str]:
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
    paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 40]
    if not paragraphs:
        return text[:1500]
    if len(paragraphs) <= 3:
        return "\n\n".join(paragraphs)[:1800]
    lead = paragraphs[0] + "\n\n" + paragraphs[1]
    tail = paragraphs[-1]
    combined = lead + "\n\n[...]\n\n" + tail
    words = combined.split()
    return " ".join(words[:max_words]) if len(words) > max_words else combined


class EvidenceRetriever:

    def __init__(self, chunks: list[str]):
        self.chunks = chunks
        self.use_bm25 = False
        try:
            from rank_bm25 import BM25Okapi

            tokenized = [re.findall(r"\w+", c.lower()) for c in self.chunks]
            self.bm25 = BM25Okapi(tokenized)
            self.use_bm25 = True
        except ImportError:
            pass

    def retrieve_top_k(self, sentence: str, k: int = 2) -> list[tuple[int, str]]:
        if len(self.chunks) <= k:
            return list(enumerate(self.chunks))
        tokens = re.findall(r"\w+", sentence.lower())
        if self.use_bm25:
            scores = self.bm25.get_scores(tokens)
            top_idx = sorted(
                range(len(scores)), key=lambda i: scores[i], reverse=True
            )[:k]
        else:
            token_set = set(tokens)
            scores = [
                len(token_set.intersection(set(re.findall(r"\w+", c.lower()))))
                for c in self.chunks
            ]
            top_idx = sorted(
                range(len(scores)), key=lambda i: scores[i], reverse=True
            )[:k]
        return [(idx, self.chunks[idx]) for idx in top_idx]


# -------------------------------------------------------------
# 4. FASTAPI SERVICE LIFECYCLE
# -------------------------------------------------------------
EVALUATOR_INSTANCE = None
UNIEVAL_MODULES: dict[str, Any] = {}
CONCURRENCY_SEMAPHORE = asyncio.Semaphore(4)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global EVALUATOR_INSTANCE, UNIEVAL_MODULES
    unieval_dir = os.getenv("UNIEVAL_DIR", "/tmp/unieval")
    sys.path.insert(0, unieval_dir)
    try:
        from metric.evaluator import get_evaluator
        from utils import convert_to_json

        UNIEVAL_MODULES["get_evaluator"] = get_evaluator
        UNIEVAL_MODULES["convert_to_json"] = convert_to_json
    except ImportError as e:
        print(f"[FASTAPI] ❌ Failed to load UniEval from {unieval_dir}: {e}")
        raise e

    cores = os.cpu_count() or 2
    torch.set_num_threads(cores)

    print(
        f"[FASTAPI] 🤖 Initializing UniEval (T5-Large) with {cores} threads on device='cpu'..."
    )
    EVALUATOR_INSTANCE = get_evaluator(
        "summarization", max_length=1024, device="cpu"
    )
    print(
        "[FASTAPI] ✅ UniEval service warm and listening on http://127.0.0.1:9933"
    )
    yield
    print("[FASTAPI] 🛑 Shutting down UniEval service.")


app = FastAPI(title="UniEval Quality Microservice", lifespan=lifespan)


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


def compute_unieval_sync(
    source_text: str, summary_text: str
) -> dict[str, Any]:
    convert_to_json = UNIEVAL_MODULES["convert_to_json"]
    evaluator = EVALUATOR_INSTANCE

    # 1. Fluency
    data_flu = convert_to_json(output_list=[summary_text])
    eval_flu = evaluator.evaluate(data_flu, dims=["fluency"], overall=False)
    fluency = round(eval_flu[0]["fluency"], 3)

    # 2. Coherence
    macro_ctx = extract_macro_skeleton(source_text, max_words=380)
    data_coh = convert_to_json(output_list=[summary_text], src_list=[macro_ctx])
    eval_coh = evaluator.evaluate(data_coh, dims=["coherence"], overall=False)
    coherence = round(eval_coh[0]["coherence"], 3)

    # 3. Chunked Sentence-Level Consistency
    chunks = chunk_document(source_text, chunk_words=380, stride_words=80)
    sentences = split_sentences(summary_text) or [summary_text]

    retriever = EvidenceRetriever(chunks)
    eval_src, eval_out, pair_meta = [], [], []

    for s_idx, sentence in enumerate(sentences):
        for c_idx, chunk in retriever.retrieve_top_k(sentence, k=2):
            eval_src.append(chunk)
            eval_out.append(sentence)
            pair_meta.append((s_idx, c_idx))

    data_cons = convert_to_json(output_list=eval_out, src_list=eval_src)
    cons_res = evaluator.evaluate(
        data_cons, dims=["consistency"], overall=False
    )

    sentence_scores: dict[int, float] = {}
    sentence_chunk_map: dict[int, int] = {}
    for idx, r in enumerate(cons_res):
        s_idx, c_idx = pair_meta[idx]
        sc = r["consistency"]
        if s_idx not in sentence_scores or sc > sentence_scores[s_idx]:
            sentence_scores[s_idx] = sc
            sentence_chunk_map[s_idx] = c_idx

    sentence_details = []
    supported_chunks = set()
    for s_idx, sentence in enumerate(sentences):
        sc = round(sentence_scores.get(s_idx, 0.0), 3)
        c_idx = sentence_chunk_map.get(s_idx, 0)
        supported = sc >= 0.50
        if supported:
            supported_chunks.add(c_idx)
        sentence_details.append(
            {
                "sentence_index": s_idx + 1,
                "text": sentence,
                "score": sc,
                "matched_chunk": c_idx + 1,
                "supported": supported,
            }
        )

    avg_consistency = (
        round(sum(s["score"] for s in sentence_details) / len(sentence_details), 3)
        if sentence_details
        else 0.0
    )
    coverage_pct = round((len(supported_chunks) / len(chunks)) * 100, 1)

    return {
        "overall_consistency": avg_consistency,
        "coherence": coherence,
        "fluency": fluency,
        "document_chunks_total": len(chunks),
        "document_chunks_covered": len(supported_chunks),
        "chunk_coverage_percent": coverage_pct,
        "sentence_breakdown": sentence_details,
    }


@app.post("/v1/evaluate")
async def evaluate_article(req: EvaluationRequest):
    if not EVALUATOR_INSTANCE:
        raise HTTPException(status_code=503, detail="Evaluator not loaded")

    t_start = time.perf_counter()
    stat_start_total, stat_start_idle = HardwareSampler.read_cpu_stat()

    async with CONCURRENCY_SEMAPHORE:
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

    epoch_ms = int(time.time() * 1000)
    event_id = generate_event_id(
        req.runner_name, req.shard_id, epoch_ms, "QUALITY_EVALUATION_COMPLETED"
    )

    event_payload = {
        "eventId": event_id,
        "eventType": "QUALITY_EVALUATION_COMPLETED",
        "timestamp": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch_ms / 1000)
        ),
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

    return {"status": "success", "event": event_payload, "metrics": metrics}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9933, log_level="info")
