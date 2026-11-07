"""Are named sentence archives extracted where the real legacy tokenizer resolves them?"""

import io
import zipfile
from pathlib import Path

from summary_evaluator.source_coverage.contracts.service_settings import CoverageSentenceResources
from summary_evaluator.source_coverage.prepare_resources import atomic_write, extract_sentences


def test_named_sentence_files_use_the_public_tokenizer_layout(tmp_path: Path) -> None:
    name = "punkt_tab/english/abbrev_types.txt"
    selected = CoverageSentenceResources(
        archive_url="https://example.invalid/punkt_tab.zip",
        archive_sha256="0" * 64,
        max_archive_bytes=1024,
        download_timeout_ms=1000,
        language="english",
        files=(name,),
    )
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(name, "dr\n")
        archive.writestr("unselected.txt", "not a named resource")
    path = tmp_path / "sentences.zip"
    atomic_write(path, stream.getvalue())
    extract_sentences(path, tmp_path / "sentences", selected)
    assert (tmp_path / "sentences" / "tokenizers" / name).read_text(encoding="utf-8") == "dr\n"
    assert not (tmp_path / "sentences" / "unselected.txt").exists()
