"""Which probabilities does llama-server return under a grammar, and does it honour `n_probs`?

A margin rule rests on the answer. If the returned numbers are already shaped by
the grammar they sum to 1 over the legal tokens, renormalising them is a no-op,
and a column meant to say "the grammar chose and the model did not" says nothing.
If they are the model's own distribution the signal is real and readable.

It stands the server up through `idhazh.llm.server.server_argv` off the entry
`config/` names, so the flags are the ones production uses and a reading cannot
be taken against weights the config no longer declares. The port comes from
`LLAMA_PORT`, read back through `idhazh.llm.server.DEFAULT_PORT` - this file
spells no llama-server flag of its own (Guardrail #6).

No fixture can answer this: what a build does with a request field is a property
of that build, so it takes a server. The reading it prints belongs in
`docs/reference/benchmarks/which-probabilities-the-server-returns.md`.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from idhazh import config
from idhazh.llm.server import (
    DEFAULT_PORT,
    completion_url,
    derive_turn_markers,
    props_url,
    render_prompt,
    server_argv,
)

LOG = logging.getLogger("measure_probability_mode")

#: A grammar of three literals, which is the shape a verdict caller uses. The
#: question is about what comes back beside the word, so the words themselves
#: only have to be few and distinguishable.
GRAMMAR = 'root ::= "YES" | "NO" | "UNCLEAR"'

#: A question the model has an opinion about, rendered in the turn markers the
#: configured weights declare. It is written here rather than read off an item:
#: an article would make the reading depend on which day it was taken.
QUESTION = (
    "A: Example Lab publishes a smaller inference model.\n"
    "B: Example Lab releases a compact model under a permissive licence.\n"
    "Are these the same story?"
)
INSTRUCTION = "Answer with one word: YES, NO or UNCLEAR."


def _ask(url: str, payload: dict[str, Any] | None, *, timeout: float) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    outbound = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if data else "GET",
    )
    with urllib.request.urlopen(outbound, timeout=timeout) as reply:
        parsed = json.loads(reply.read().decode("utf-8"))
    return parsed if isinstance(parsed, dict) else {}


def _wait_for_health(process: subprocess.Popen[bytes], *, url: str, limit_s: float) -> float:
    """How long the weights took to load, or a refusal naming which happened."""
    started = time.monotonic()
    while time.monotonic() - started < limit_s:
        if process.poll() is not None:
            raise RuntimeError(f"the server exited with {process.returncode} before /health")
        try:
            if _ask(url, None, timeout=5.0).get("status") == "ok":
                return time.monotonic() - started
        except (OSError, TimeoutError, json.JSONDecodeError):
            time.sleep(2.0)
    raise TimeoutError(f"the server never answered {url}")


def _window(reply: dict[str, Any]) -> list[dict[str, Any]]:
    """The server's alternatives at the first decoded position, or none."""
    positions = reply.get("completion_probabilities") or []
    if not isinstance(positions, list) or not positions:
        return []
    alternatives = positions[0].get("top_logprobs") or []
    return alternatives if isinstance(alternatives, list) else []


def _reading(reply: dict[str, Any]) -> dict[str, Any]:
    """One run, reduced to what the question needs and nothing the page cannot print."""
    alternatives = _window(reply)
    probabilities = [
        float(entry["prob"]) if "prob" in entry else math.exp(float(entry["logprob"]))
        for entry in alternatives
    ]
    return {
        "content": reply.get("content"),
        "returned": len(alternatives),
        "entries": [
            {
                "token": entry.get("token"),
                "logprob": entry.get("logprob"),
                "prob": entry.get("prob"),
            }
            for entry in alternatives[:5]
        ],
        "mass": round(sum(probabilities), 6),
        "illegal_in_window": sorted(
            {
                str(entry.get("token"))
                for entry in alternatives
                if not any(
                    str(entry.get("token")).strip() and word.startswith(str(entry["token"]).strip())
                    for word in ("YES", "NO", "UNCLEAR")
                )
            }
        ),
    }


def _body(
    prompt: str, *, alternatives: int, post_sampling: bool, grammar: str | None
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "prompt": prompt,
        "temperature": 0.0,
        "top_p": 1.0,
        "seed": 0,
        "n_predict": 4,
        "n_probs": alternatives,
        "post_sampling_probs": post_sampling,
        "stream": False,
        "cache_prompt": True,
    }
    if grammar is not None:
        payload["grammar"] = grammar
    return payload


def measure(
    *,
    binary: Path,
    weights: Path,
    config_root: Path,
    role: str,
    port: int,
    runs: int,
    alternatives: int,
) -> dict[str, Any]:
    """Stand the server up, ask the same question six ways, and report what came back."""
    settings = config.load(config_root)
    entry = getattr(settings.models, role)
    if weights.name != Path(entry.file).name:
        raise SystemExit(
            f"config names {Path(entry.file).name} and the command line names {weights.name} - "
            "a reading taken against weights the config does not declare is not a reading"
        )
    argv = server_argv(
        binary=binary, weights=weights, model=entry, server=entry.server, port=port
    )
    # Both routes are derived from one address, so the port the server was
    # started on and the port a request goes to cannot disagree.
    base = f"http://127.0.0.1:{port}/v1/chat/completions"
    endpoint = completion_url(base)
    health = f"http://127.0.0.1:{port}/health"
    record: dict[str, Any] = {
        "weights": weights.name,
        "sha256": entry.sha256,
        "asked_n_probs": alternatives,
        "grammar": GRAMMAR,
        "runs": runs,
    }
    process = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        record["load_s"] = round(_wait_for_health(process, url=health, limit_s=900.0), 1)
        record["build_info"] = _ask(props_url(base), None, timeout=30.0).get("build_info")
        # After the wait, because the markers are this server's own rendering.
        prompt = render_prompt(
            system=INSTRUCTION,
            user=QUESTION,
            markers=derive_turn_markers(base, entry=entry, timeout=60.0),
        )
        for post_sampling in (False, True):
            record[f"post_sampling_probs={post_sampling}"] = [
                _reading(
                    _ask(
                        endpoint,
                        _body(
                            prompt,
                            alternatives=alternatives,
                            post_sampling=post_sampling,
                            grammar=GRAMMAR,
                        ),
                        timeout=600.0,
                    )
                )
                for _ in range(runs)
            ]
        record["no_grammar"] = _reading(
            _ask(
                endpoint,
                _body(prompt, alternatives=alternatives, post_sampling=False, grammar=None),
                timeout=600.0,
            )
        )
    finally:
        process.terminate()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=Path("backend/bin/llama-server"))
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    parser.add_argument("--role", default="summarize")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--alternatives", type=int, default=25)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    record = measure(
        binary=args.binary,
        weights=args.weights,
        config_root=args.config_root,
        role=args.role,
        port=DEFAULT_PORT,
        runs=args.runs,
        alternatives=args.alternatives,
    )
    rendered = json.dumps(record, indent=2, sort_keys=True)
    if args.out is not None:
        args.out.write_text(rendered + "\n", encoding="utf-8")
    LOG.info("%s", rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
