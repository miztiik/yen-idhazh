"""The training notebook is executable content, so its gates are tested like any other.

None of this runs the notebook - that needs a GPU and a network, and Rule #7
forbids a test that fetches anything. What it does test is the four properties
row 6 states, each of which fails silently if it ever stops holding:

- Every cell parses. A notebook nobody can run is worse than no notebook.
- No model is named. The teacher is `finetune.teacher`, a key in `models`, so a
  config swap moves the notebook with it. A hardcoded name is stale the day the
  config moves and nothing would say so.
- The loader refuses rather than warns. Training on the corpus holdout or on the
  reference set's own test slice produces a model that measures well and is
  worthless, and neither leaves a trace.
- The mask is asserted rather than configured. Without it about six sevenths of
  the gradient goes into learning to write other people's news articles.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, Final

import pytest

#: A parsed `.ipynb`. Only `cells` and each cell's `cell_type` and `source` are
#: read here, so anything richer would be a shape this file does not check.
type Notebook = dict[str, Any]

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
NOTEBOOK: Final = REPO_ROOT / "notebooks" / "finetune.ipynb"

#: A name here means somebody stopped reading the teacher out of config.
MODEL_NAMES: Final = ("qwen", "llama", "mistral", "gemma", "phi-3", "deepseek")

#: llama.cpp is the inference engine and the merge tool. It is not a model, and
#: the notebook has to name it to say how the merge is done.
NOT_A_MODEL: Final = (
    "llama.cpp",
    "llama-export-lora",
    "llama-quantize",
    "convert_lora_to_gguf",
)


@pytest.fixture(scope="module")
def notebook() -> Notebook:
    loaded: Notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    return loaded


@pytest.fixture(scope="module")
def code_cells(notebook: Notebook) -> list[str]:
    return [
        "".join(cell["source"])
        for cell in notebook["cells"]
        if cell["cell_type"] == "code"
    ]


@pytest.fixture(scope="module")
def every_cell(notebook: Notebook) -> str:
    """Markdown and code as a person reads them, not as JSON escapes them."""
    return "\n".join("".join(cell["source"]) for cell in notebook["cells"])


def test_every_code_cell_parses(code_cells: list[str]) -> None:
    for number, source in enumerate(code_cells, start=1):
        ast.parse(source, filename=f"finetune.ipynb cell {number}")


def test_no_model_is_named_anywhere_in_it(every_cell: str) -> None:
    """The teacher is a config key, so the notebook survives a model swap (row 6 decision 1)."""
    body = every_cell.lower()
    for tool in NOT_A_MODEL:
        body = body.replace(tool, "")
    named = [name for name in MODEL_NAMES if name in body]

    assert not named, (
        f"{named} appears in the notebook. It must resolve finetune.teacher against "
        f"config/idhazh.json instead - models.summarize already moved once."
    )


def test_it_reads_the_teacher_and_the_row_counts_out_of_config(code_cells: list[str]) -> None:
    """A number typed into the notebook is a number that disagrees with the config (Rule #6)."""
    body = "\n".join(code_cells)

    for key in ("teacher", "train_rows", "min_rows", "epochs", "sequence_length"):
        assert f'FINETUNE["{key}"]' in body, f"finetune.{key} is not read from config"


@pytest.mark.parametrize(
    ("hazard", "needle"),
    [
        ("the corpus holdout", "holdout"),
        ("the reference set's test slice", "reference_test"),
        ("an injection marker in a training target", "canary_markers"),
    ],
)
def test_the_loader_refuses_every_row_it_may_not_train_on(
    code_cells: list[str], hazard: str, needle: str
) -> None:
    body = "\n".join(code_cells)

    assert needle in body, f"nothing in the notebook looks at {hazard}"


def test_a_leak_stops_the_run_rather_than_warning_about_it(code_cells: list[str]) -> None:
    """`print` here would be a model that measures well and is worthless."""
    body = "\n".join(code_cells)

    assert "leaked = " in body and "raise SystemExit" in body
    for line in body.splitlines():
        if "leaked" in line and "print(" in line:
            pytest.fail(f"a leak is reported rather than raised: {line.strip()}")


def test_the_loss_mask_is_asserted_on_a_real_batch(code_cells: list[str]) -> None:
    """Row 6's oracle. The mask is decoded and checked before a step runs."""
    body = "\n".join(code_cells)

    assert "IGNORE = -100" in body
    assert "unmasked" in body, "nothing decodes the positions the run will learn from"
    assert "json.loads(learned_text)" in body, "the unmasked span is never parsed"
    assert "share > 0.5" in body, "nothing checks the unmasked span is not the article"


def test_it_drops_an_over_length_row_instead_of_truncating_it(code_cells: list[str]) -> None:
    """A truncated target teaches the model to stop mid-summary."""
    body = "\n".join(code_cells)

    assert "too_long" in body
    assert "Dropped, not truncated." in body


def test_the_merge_is_not_attempted_on_the_free_tier(every_cell: str) -> None:
    """Merging wants ~16 GB of ordinary RAM against the free tier's 12 (row 6 decision 5)."""
    assert "llama-export-lora" in every_cell, "the notebook does not say how to merge"
    assert "merge_and_unload" not in every_cell, "it merges in Colab, which dies on the save"


def test_no_token_is_committed(every_cell: str) -> None:
    """The notebook is public. A token reaches it only from the runtime's own secrets."""
    assert 'userdata.get("HF_TOKEN")' in every_cell, "the token is not read from a secret store"

    for line in every_cell.splitlines():
        stripped = line.strip()
        if stripped.startswith(("HF_TOKEN", "token = \"", "token = '")):
            pytest.fail(f"a token looks assigned in the notebook: {stripped}")
