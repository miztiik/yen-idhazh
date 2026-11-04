"""How are the pinned local tokenizer and sentence rules used without model weights?"""

import hashlib
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from pydantic import TypeAdapter

from .contracts.unieval_error import UnievalError
from .contracts.unieval_settings import UnievalSettings
from .fail_unieval import UnievalFailure
from .load_model import quiet_model_output
from .load_model_assets import resolve_snapshot


class PromptTokenizer(Protocol):
    def encode(self, text: str, *, add_special_tokens: bool = True) -> list[int]: ...
    def __call__(
        self, text: str, *, add_special_tokens: bool, return_offsets_mapping: bool
    ) -> dict[str, object]: ...


class SentenceSplitter(Protocol):
    def tokenize(self, text: str) -> list[str]: ...


class TokenizerLoader(Protocol):
    def from_pretrained(
        self, path: str, *, local_files_only: bool, use_fast: bool
    ) -> PromptTokenizer: ...


@dataclass(frozen=True)
class UnievalResources:
    tokenizer: PromptTokenizer
    sentences: SentenceSplitter
    snapshot: Path

    def token_count(self, prompt: str) -> int:
        return len(self.tokenizer.encode(prompt, add_special_tokens=True))

    def source_offsets(self, source: str) -> list[tuple[int, int]]:
        encoded = self.tokenizer(source, add_special_tokens=False, return_offsets_mapping=True)
        offsets = TypeAdapter(list[tuple[int, int]]).validate_python(
            encoded["offset_mapping"], strict=True
        )
        if not offsets or any(
            start < 0 or end < start or end > len(source) for start, end in offsets
        ):
            raise UnievalFailure(UnievalError.from_code("TOKENIZER_FAILED"))
        return offsets


def read_sentence_directory(settings: UnievalSettings, root: Path) -> Path:
    cache = root / settings.assets.cache_directory / "sentences"
    archive = cache / "punkt_tab.zip"
    selected = settings.assets.sentences
    if archive.stat().st_size > selected.max_archive_bytes:
        raise ValueError("The pinned sentence archive exceeds its declared allowance")
    if hashlib.sha256(archive.read_bytes()).hexdigest() != selected.archive_sha256:
        raise ValueError("The pinned sentence archive digest does not match")
    with zipfile.ZipFile(archive) as source:
        for name in selected.files:
            info = source.getinfo(name)
            if info.file_size > selected.max_archive_bytes:
                raise ValueError("A named sentence resource exceeds its declared allowance")
            if (cache / name).read_bytes() != source.read(name):
                raise ValueError("The prepared sentence resource differs from its pinned archive")
    return cache / "punkt_tab" / selected.language


def load_unieval_resources(settings: UnievalSettings, root: Path) -> UnievalResources:
    try:
        with quiet_model_output():
            from nltk.tokenize.punkt import PunktSentenceTokenizer, load_punkt_params
            from transformers import AutoTokenizer

            files = tuple(
                name for name in settings.assets.model.files if name != "pytorch_model.bin"
            )
            selection = settings.assets.model.model_copy(update={"files": files})
            snapshot = resolve_snapshot(
                selection, root / settings.assets.cache_directory, local_only=True
            )
            tokenizer = cast(TokenizerLoader, AutoTokenizer).from_pretrained(
                str(snapshot), local_files_only=True, use_fast=True
            )
            splitter = cast(
                SentenceSplitter,
                PunktSentenceTokenizer(load_punkt_params(read_sentence_directory(settings, root))),
            )
            return UnievalResources(tokenizer, splitter, snapshot)
    except (OSError, ValueError, LookupError, KeyError, zipfile.BadZipFile):
        raise UnievalFailure(UnievalError.from_code("TOKENIZER_FAILED")) from None
