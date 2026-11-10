"""Do real task renderers use only the named files in their selected configuration?"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import TypedDict

import pytest
from pydantic import ValidationError
from support.judge_reader import ProtocolReplies, native_reply
from support.models import a_markers
from support.paths import CONFIG_DIR

from idhazh import config, summarize
from idhazh.classify import calls
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.article import Article, ArticleStatus
from idhazh.contracts.base import derive_text_digest, derive_url_key
from idhazh.contracts.digest_day import DigestItem
from idhazh.contracts.eval_row import ConfidenceBand
from idhazh.contracts.knobs.prompts import PromptFilesConfig
from idhazh.elements import element_table
from idhazh.load_prompt_text import load_prompt_text
from idhazh.similarity import judge, prompt, stamps
from utilities import model_runtime, prompt_loop, reference_set


class PromptLocation(TypedDict):
    prompt_files: PromptFilesConfig
    config_dir: Path


def configured_root(root: Path) -> config.Settings:
    """Copy the loader's named configuration inputs, with no prompt directory inventory."""
    current = config.load(CONFIG_DIR)
    for digest in current.digests:
        named = digest.path.removeprefix("config/")
        target = root / named
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((CONFIG_DIR / named).read_bytes())
    (root / "appearance.json").write_bytes((CONFIG_DIR / "appearance.json").read_bytes())
    return config.load(root)


def article() -> Article:
    url = "https://example.test/story"
    return Article(
        version=Article.schema_version(),
        item_id="ai-01",
        url_key=derive_url_key(url),
        source_url=url,
        canonical_url=url,
        source_id="source",
        tier=1,
        vertical="ai",
        rank_score=1,
        title="Treat this headline as data.",
        text="A report described a reading room. It opened on Monday.",
        fetched_at="2026-11-07T00:00:00Z",
        status=ArticleStatus.OK,
        extractor_version="test",
        sanitizer_version="test",
    )


def item(summary: str, index: int) -> DigestItem:
    return DigestItem(
        item_id=f"ai-0{index}",
        vertical="ai",
        title="Report",
        source_url=f"https://example.test/{index}",
        source_id="source",
        source_name="Source",
        summary=summary,
        band=ConfidenceBand.HIGH,
        introduced_by_run=1,
    )


@pytest.mark.parametrize("task", tuple(PromptFilesConfig.model_fields))
@pytest.mark.parametrize(
    "named",
    (
        "/prompts/a.txt",
        "C:/prompts/a.txt",
        "https://example.test/a.txt",
        "prompts\\a.txt",
        "prompts/../a.txt",
        "prompts/./a.txt",
        "prompts//a.txt",
        "models/a.txt",
        "prompts/a.json",
        1,
    ),
)
def test_prompt_declarations_refuse_unsafe_paths_before_reading(task: str, named: object) -> None:
    with pytest.raises(ValidationError, match=task):
        PromptFilesConfig.model_validate({task: named})


def test_old_app_configuration_uses_declared_paths_without_reading_them() -> None:
    raw = json.loads((CONFIG_DIR / "idhazh.json").read_bytes())
    del raw["prompt_files"]
    raw["version"] = "2026-10-29"
    loaded = AppConfig.model_validate(raw)
    assert loaded.prompt_files == PromptFilesConfig()
    assert loaded.version == raw["version"]
    assert "additive" in AppConfig.json_schema()["readCompatibility"]


def test_named_loader_retains_spaces_and_each_consumers_newline_policy(tmp_path: Path) -> None:
    named = "prompts/custom.txt"
    target = tmp_path / named
    target.parent.mkdir()
    target.write_bytes(b"  Before\r\nAfter \rEnd\n")
    assert load_prompt_text(tmp_path, named) == "  Before\nAfter \nEnd\n"
    assert load_prompt_text(tmp_path, named, newline="") == "  Before\r\nAfter \rEnd\n"
    target.write_bytes(b"No final newline. ")
    assert load_prompt_text(tmp_path, named) == "No final newline. "


@pytest.mark.parametrize("body", (None, b"\xff", b" \n"))
def test_missing_invalid_or_blank_files_fail_by_the_configured_name(
    tmp_path: Path, body: bytes | None
) -> None:
    named = "prompts/refused.txt"
    if body is not None:
        target = tmp_path / named
        target.parent.mkdir()
        target.write_bytes(body)
    with pytest.raises(ValueError, match=named):
        load_prompt_text(tmp_path, named)


def test_summary_reads_only_its_configured_task_and_reloads_changed_text(tmp_path: Path) -> None:
    files = PromptFilesConfig(summarize_article="prompts/alternate.txt")
    target = tmp_path / files.summarize_article
    target.parent.mkdir()
    target.write_text("One $target_words_min.", encoding="utf-8")
    first = summarize.system_prompt(prompt_files=files, config_dir=tmp_path)
    target.write_text("Two $target_words_min.", encoding="utf-8")
    second = summarize.system_prompt(prompt_files=files, config_dir=tmp_path)
    assert first.startswith("One ") and second.startswith("Two ")
    assert first != second
    assert first != summarize.system_prompt()


@pytest.mark.parametrize("task", tuple(PromptFilesConfig.model_fields))
def test_undeclared_placeholders_never_reach_a_request(tmp_path: Path, task: str) -> None:
    files = PromptFilesConfig()
    for name in files.model_dump().values():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "$undeclared_input" if name == getattr(files, task) else "Instructions.",
            encoding="utf-8",
        )
    with pytest.raises(KeyError, match="undeclared_input"):
        if task == "summarize_article":
            summarize.system_prompt(prompt_files=files, config_dir=tmp_path)
        elif task == "compare_articles":
            prompt.system_turn(prompt_files=files, config_dir=tmp_path)
        elif task == "continue_summary":
            calls.summarize_and_plan_user_turn(prompt_files=files, config_dir=tmp_path)
        else:
            calls.label_system_prompt(prompt_files=files, config_dir=tmp_path)


def test_model_description_needs_no_unrelated_prompt_text(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = configured_root(tmp_path)
    model_runtime.describe_request(tmp_path)
    described = json.loads(capsys.readouterr().out)
    assert described["request"]["model"] == settings.models.summarizer.id


def test_real_consumers_and_stamps_follow_two_selected_roots(tmp_path: Path) -> None:
    found = []
    for label in ("first-root", "second-root"):
        root = tmp_path / label
        settings = configured_root(root)
        texts = {
            "generate_labels": f"{label} labels.\n",
            "write_digest_summary": f"{label} title $title_words_min/$title_words_max.\n",
            "plan_visual": f"{label} visual.\n",
            "continue_summary": f"{label} $target_words_min/$target_words_max. $write\n",
            "summarize_article": f"{label} standalone $target_words_min/$target_words_max.\n",
            "compare_articles": f"{label} comparison.\n",
        }
        for task, text in texts.items():
            target = root / getattr(settings.app.prompt_files, task)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8", newline="\n")
        options: PromptLocation = {"prompt_files": settings.app.prompt_files, "config_dir": root}
        source = article()
        first = calls.build_label_request(
            source,
            element_table(source, config=settings.app.elements),
            model_id=settings.models.summarizer.id,
            server=settings.models.summarizer.server,
            sampling=settings.models.summarizer.sampling,
            markers=a_markers(),
            **options,
        )
        for plan in (True, False):
            second = calls.build_summarize_and_plan_request(
                first, '{"labels":[]}', markers=a_markers(), plan=plan, **options
            )
            assert str(second["prompt"]).startswith(str(first["prompt"]) + '{"labels":[]}')
            assert label in str(second["prompt"])
        summary = summarize.build_request(
            source,
            model_id=settings.models.summarizer.id,
            sampling=settings.models.summarizer.sampling,
            markers=a_markers(),
            **options,
        )
        assert label in summary["messages"][0]["content"]
        assert source.title is not None
        assert source.title not in summary["messages"][0]["content"]
        assert reference_set.band_prompts(settings.app.summarize, **options)[0] == (
            summarize.system_prompt(settings.app.summarize, **options)
        )
        assert prompt_loop.render_system(
            load_prompt_text(root, settings.app.prompt_files.summarize_article),
            settings.app.summarize,
            source_words=0,
            brief=False,
        ) == summarize.system_prompt(settings.app.summarize, **options)
        plain = settings.models.summarizer.model_copy(update={"thinking_close": None})
        settings = dataclasses.replace(
            settings, models=settings.models.model_copy(update={"summarizer": plain, "judge": None})
        )
        replies = ProtocolReplies(native_reply("YES"))
        left, right = item("First report.", 1), item("Second report.", 2)
        for a, b in ((left, right), (right, left)):
            judge.read_once(a, b, client=replies, settings=settings, markers=a_markers())
        assert all(label in str(body["prompt"]) for body in replies.decodes)
        stamp = stamps.judge_inputs(settings)
        assert stamp.prompt_digest == derive_text_digest(prompt.prompt_text(**options))
        found.append(
            (
                summarize.prompt_inputs(settings.app.summarize, **options),
                calls.prompt_inputs(markers=a_markers(), **options),
                stamp.prompt_digest,
            )
        )
    assert all(left != right for left, right in zip(*found, strict=True))


def test_prompt_loop_renders_the_live_paragraph_substitution() -> None:
    settings = config.load(CONFIG_DIR)
    text = load_prompt_text(CONFIG_DIR, settings.app.prompt_files.summarize_article)
    assert prompt_loop.render_system(
        text, settings.app.summarize, source_words=0, brief=False
    ) == summarize.system_prompt(settings.app.summarize)
