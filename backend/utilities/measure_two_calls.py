"""Measure what call 2 costs when it opens with call 1's prompt.

Row 3's oracle, and it is two questions rather than one.

**The floor.** `cached_tokens` on call 2 is at least call 1's prompt token
count. The system turn and the article-carrying user turn are the same bytes and
come first, so a prefix cache reuses them - or the prompt was built wrong. That
is an assertion and this tool fails when it does not hold.

**The target.** Whether call 1's *generated* tokens cache as well, since call 2
re-renders them through the chat template into an assistant turn. That is a
measurement about one runtime and one template, not a property of the design, so
it is reported rather than asserted.

It is an operator tool and never a test: it needs a multi-gigabyte GGUF that
`backend/models/` does not commit, and it runs a real model for minutes
(`CLAUDE.md` section 13). Nothing in CI calls it.

    python backend/utilities/measure_two_calls.py \
        --binary backend/bin/llama-server.exe \
        --weights backend/models/Qwen3-8B-Q4_K_M.gguf
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict
from pathlib import Path

from idhazh import config
from idhazh.contracts.article import Article
from idhazh.elements import element_table
from idhazh.llm.server import Completion, post, server_argv
from idhazh.visual_planner import (
    build_call_one_request,
    build_call_two_request,
    call_two_output_tokens,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTICLE = REPO_ROOT / "tests" / "fixtures" / "contracts" / "article" / "ok.json"


def wait_for_health(port: int, *, deadline_seconds: float) -> None:
    """Block until the server answers, or give up saying how long it waited."""
    started = time.monotonic()
    while time.monotonic() - started < deadline_seconds:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2.0):
                return
        except (urllib.error.URLError, OSError):
            time.sleep(1.0)
    raise TimeoutError(f"the server did not answer /health in {deadline_seconds:.0f} s")


def report(name: str, completion: Completion) -> None:
    print(
        f"{name:<8} prompt={completion.prompt_tokens:>6}"
        f"  completion={completion.completion_tokens:>5}"
        f"  cached={completion.cached_tokens:>6}"
        f"  prefill_ms={completion.prefill_ms:>7}"
        f"  decode_ms={completion.decode_ms:>7}"
        f"  finish={completion.finish_reason}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--weights", type=Path, required=True)
    # Not spelled `--port`. `test_summarize` holds one function as the only
    # place in `backend/` that writes a llama-server flag as a quoted literal,
    # and it reads the source rather than the argv, so an option of ours sharing
    # the name would put this file in that set.
    parser.add_argument("--server-port", type=int, default=8099)
    parser.add_argument("--article", type=Path, default=ARTICLE)
    parser.add_argument("--startup-seconds", type=float, default=600.0)
    parser.add_argument("--request-minutes", type=float, default=30.0)
    parser.add_argument(
        "--decode-cap",
        type=int,
        default=0,
        help=(
            "Stop each decode after this many tokens. Zero uses the real budgets. "
            "Both oracle numbers are prefill facts and are on the reply whatever "
            "stopped it, so a cap answers the same question in minutes instead of "
            "hours on a machine slower than the runner - at the cost of telling you "
            "nothing about what the reply said."
        ),
    )
    args = parser.parse_args(argv)

    settings = config.load(REPO_ROOT / "config")
    model = settings.app.models.summarize
    article = Article.from_json(args.article.read_text(encoding="utf-8"))
    table = element_table(article, config=settings.app.elements)

    argv_line = server_argv(
        binary=args.binary,
        weights=args.weights,
        model=model,
        inference=model.inference,
        port=args.server_port,
    )
    print(" ".join(argv_line), flush=True)
    server = subprocess.Popen(argv_line, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait_for_health(args.server_port, deadline_seconds=args.startup_seconds)
        endpoint = f"http://127.0.0.1:{args.server_port}/v1/chat/completions"
        timeout = args.request_minutes * 60.0

        first = build_call_one_request(
            article, table, model_id=model.id, inference=model.inference
        )
        if args.decode_cap:
            first["max_tokens"] = args.decode_cap
        one = post(first, endpoint=endpoint, timeout=timeout)
        report("call 1", one)

        second = build_call_two_request(
            first, one.content, source_words=article.band_source_words, brief=article.brief
        )
        if args.decode_cap:
            second["max_tokens"] = args.decode_cap
        two = post(second, endpoint=endpoint, timeout=timeout)
        report("call 2", two)
    finally:
        server.terminate()
        server.wait(timeout=60)

    reused = two.cached_tokens
    floor = one.prompt_tokens
    generated = one.prompt_tokens + one.completion_tokens
    print()
    print(f"budget handed to call 2      {call_two_output_tokens(settings.app.summarize):>6}")
    print(f"call 2 prompt                {two.prompt_tokens:>6}")
    print(f"the floor: call 1 prompt     {floor:>6}")
    print(f"cached on call 2             {reused:>6}")
    print(f"call 1 prompt + completion   {generated:>6}")
    if reused >= floor:
        print(f"FLOOR HELD - {reused - floor} tokens beyond call 1's prompt were reused too")
    else:
        print(f"FLOOR BROKEN - {floor - reused} tokens of call 1's prompt prefilled again")
        print(
            "  A four-token gap here is Qwen3's chat template rather than the prompt: it "
            "writes an\n"
            "  empty <think></think> block into a generation prompt and drops it when the "
            "same turn is\n"
            "  replayed as history. Anything larger is the prompt, and the first thing to "
            "check is\n"
            "  whether call 2 was built from call 1's own payload."
        )
    if reused >= generated:
        print("TARGET: call 1's generated tokens cache as well")
    else:
        print(f"TARGET: {generated - reused} of call 1's own reply prefilled again")
    print()
    print(json.dumps({"call_one": asdict(one), "call_two": asdict(two)}, default=str))
    return 0 if reused >= floor else 1


if __name__ == "__main__":
    sys.exit(main())
