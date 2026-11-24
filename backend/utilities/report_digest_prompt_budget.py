"""Report what the configured digest calls cost before any article is added."""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Mapping
from http.client import HTTPException
from pathlib import Path
from urllib.request import Request

from idhazh import config
from idhazh.classify import calls
from idhazh.classify.chart_candidates import candidate_block
from idhazh.classify.dag import response_tokens
from idhazh.classify.plan_visual_request import chart_capabilities
from idhazh.contracts.knobs.models import ModelEntry
from idhazh.llm.server import (
    ProbeRefusedError,
    completion_payload,
    derive_turn_markers,
    props,
    request_timeout_seconds,
    resolve_endpoint,
    tokenize_url,
)
from idhazh.open_without_proxy import open_without_proxy

LOG = logging.getLogger(__name__)


def _tokenized_prompt_length(prompt: str, *, endpoint: str, timeout: float) -> int:
    # Native string completions add and parse special tokens. /tokenize does not
    # add them by default, so ask for the same behavior explicitly.
    outbound = Request(
        tokenize_url(endpoint),
        data=json.dumps({"content": prompt, "add_special": True, "parse_special": True}).encode(
            "utf-8"
        ),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with open_without_proxy(outbound, timeout=timeout) as response:
        body = json.load(response)
    tokens = body.get("tokens") if isinstance(body, dict) else None
    if not isinstance(tokens, list) or not tokens or any(
        type(token) is not int or token < 0 for token in tokens
    ):
        raise ValueError("the tokenizer did not return token IDs for the rendered prompt")
    return len(tokens)


def report_call_budget(
    variant: str,
    request: Mapping[str, object],
    *,
    model: ModelEntry,
    endpoint: str,
    context_window: int,
    nominal_article_tokens: int,
) -> None:
    """Count one rendered request against its receiving model, without decoding it."""
    prompt = request.get("prompt")
    if not isinstance(prompt, str) or not prompt:
        raise ValueError("the diagnostic needs a rendered completion prompt")
    reply_limit = response_tokens(request)
    input_tokens = _tokenized_prompt_length(
        prompt, endpoint=endpoint, timeout=request_timeout_seconds(model)
    )
    remaining = context_window - input_tokens - reply_limit
    allowance_fits = nominal_article_tokens <= remaining
    LOG.log(
        logging.INFO if allowance_fits else logging.WARNING,
        "digest_prompt_budget variant=%s model=%s scaffold_input_tokens=%d reply_limit_tokens=%d "
        "context_window_tokens=%d remaining_article_tokens=%d nominal_article_tokens=%d%s",
        variant, model.id, input_tokens, reply_limit, context_window, remaining,
        nominal_article_tokens,
        "" if allowance_fits else " warning=nominal_article_allowance_does_not_fit",
    )


def report_digest_budgets(settings: config.Settings) -> None:
    app = settings.app
    model = settings.models.summarizer
    endpoint = resolve_endpoint(app.model_server.base_url)
    timeout = request_timeout_seconds(model)
    generation = props(endpoint, timeout=timeout).get("default_generation_settings")
    context_window = generation.get("n_ctx") if isinstance(generation, dict) else None
    if type(context_window) is not int or context_window < 1:
        raise ProbeRefusedError("the server did not report its slot context window")
    markers = derive_turn_markers(endpoint, entry=model, timeout=timeout)
    enabled_forms = chart_capabilities(app.visuals)
    for forms in ((), enabled_forms) if enabled_forms else ((),):
        request = completion_payload(
            model_id=model.id,
            system=calls.summary_system_prompt(
                app.summarize,
                forms=forms,
                prompt_files=app.prompt_files,
                config_dir=settings.config_dir,
            ),
            user=calls.summary_user_turn("", "") + (candidate_block(()) if forms else ""),
            output_schema=calls.summarize_and_plan_schema(forms=forms),
            server=model.server,
            sampling=model.sampling,
            markers=markers,
        )
        report_call_budget(
            "summary_and_chart" if forms else "summary_only",
            request,
            model=model,
            endpoint=endpoint,
            context_window=context_window,
            nominal_article_tokens=app.extract.truncation_cap_tokens,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        report_digest_budgets(config.load(args.config_root))
    except (OSError, HTTPException, ValueError, KeyError, ProbeRefusedError) as error:
        # A server or renderer error can quote its input. Log only the failure type.
        LOG.warning("digest_prompt_budget_unavailable error_type=%s", type(error).__name__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
