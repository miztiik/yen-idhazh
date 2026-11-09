"""How are saved native files delivered as independent, complete provider reports?"""

import argparse
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from render_classifications import ClassificationReport, render_classifications
from render_report import (
    compose_report,
    render_gliner_results,
    render_spacy_results,
)
from render_tables import read_object, read_text, render_cell

# GitHub rejects a step summary larger than one MiB.
SUMMARY_MAX_BYTES = 1_048_576


@dataclass(frozen=True)
class NativeFiles:
    request: dict[str, object] | None = None
    response: dict[str, object] | None = None
    settings: dict[str, object] | None = None
    error: str | None = None


@dataclass(frozen=True)
class Reports:
    combined: str
    spacy: str
    gliner: str
    failed: bool


def write_atomic(path: Path, content: bytes) -> None:
    """Replace one run-owned artifact with complete bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def read_native_files(
    directory: Path, provider: str, error: str | None = None, *, settings: bool = True
) -> NativeFiles:
    """Read only the named files in one provider's run-owned directory."""
    payloads: dict[str, dict[str, object] | None] = {}
    errors = [error] if error is not None else []
    names = ("request.json", "response.json") + (("settings.json",) if settings else ())
    for name in names:
        try:
            payloads[name] = read_object(json.loads((directory / provider / name).read_bytes()))
        except FileNotFoundError:
            payloads[name] = None
        except (OSError, ValueError):
            payloads[name] = None
            errors.append(f"The saved {provider} {name} could not be read as native JSON.")
    return NativeFiles(
        payloads["request.json"],
        payloads["response.json"],
        payloads.get("settings.json"),
        " ".join(errors) if errors else None,
    )


def _failed(files: NativeFiles, *, spacy: bool = False) -> bool:
    return bool(
        files.error
        or files.response is None
        or "error" in files.response
        or (spacy and files.response.get("status") != "complete")
    )


def _provider_section(
    source: str,
    files: NativeFiles,
    *,
    spacy: bool,
    classification: ClassificationReport | None = None,
) -> str:
    if spacy:
        return render_spacy_results(
            source,
            None if files.error else files.response,
            spacy_error=files.error,
            spacy_request=files.request,
            spacy_settings=files.settings,
        )
    return render_gliner_results(
        source,
        None if files.error else files.response,
        gliner_error=files.error,
        gliner_request=files.request,
        gliner_settings=files.settings,
        classification=classification,
    )


def _safe_section(
    source: str,
    files: NativeFiles,
    *,
    spacy: bool,
    classification: ClassificationReport | None = None,
) -> tuple[str, bool]:
    try:
        return _provider_section(source, files, spacy=spacy, classification=classification), False
    except (KeyError, ValueError):
        provider = "spaCy" if spacy else "GLiNER"
        error = f"The saved {provider} evidence is invalid; inspect its native files."
    try:
        unavailable = NativeFiles(request=files.request, settings=files.settings, error=error)
        return _provider_section(
            source, unavailable, spacy=spacy, classification=classification
        ), True
    except (KeyError, ValueError):
        return _provider_section(
            source, NativeFiles(error=error), spacy=spacy, classification=classification
        ), True


def _safe_classifications(
    source: str, files: NativeFiles | None
) -> tuple[ClassificationReport | None, bool]:
    if files is None:
        return None, False
    try:
        return render_classifications(
            source,
            None if files.error else files.response,
            request=files.request,
            error=files.error,
        ), False
    except (KeyError, ValueError):
        error = "The saved classification evidence is invalid; inspect its native files."
    try:
        return render_classifications(source, None, request=files.request, error=error), True
    except (KeyError, ValueError):
        return render_classifications(source, None, error=error), True


def render_saved_reports(
    source: str,
    spacy: NativeFiles,
    gliner: NativeFiles,
    *,
    classification: NativeFiles | None = None,
    process_error: str | None = None,
) -> Reports:
    """Compose every output from the same pure provider sections."""
    read_text(source)
    classification_section, invalid_classification = _safe_classifications(source, classification)
    spacy_section, invalid_spacy = _safe_section(source, spacy, spacy=True)
    gliner_section, invalid_gliner = _safe_section(
        source, gliner, spacy=False, classification=classification_section
    )
    failed = (
        _failed(spacy, spacy=True)
        or _failed(gliner)
        or invalid_spacy
        or invalid_gliner
        or invalid_classification
        or (classification is not None and _failed(classification))
        or process_error is not None
    )
    footer = "\n**Process error:** " + render_cell(process_error) + "\n" if process_error else ""
    return Reports(
        compose_report(source, spacy_section, gliner_section) + footer,
        compose_report(source, spacy_section) + footer,
        compose_report(source, gliner_section) + footer,
        failed,
    )


def read_saved_reports(
    directory: Path,
    source: str | None = None,
    *,
    spacy_error: str | None = None,
    gliner_error: str | None = None,
    classification_error: str | None = None,
    process_error: str | None = None,
) -> Reports:
    spacy = read_native_files(directory, "spacy", spacy_error)
    gliner = read_native_files(directory, "gliner", gliner_error)
    classification = read_native_files(
        directory / "gliner", "classification", classification_error, settings=False
    )
    has_classification = any(
        value is not None
        for value in (
            classification.request,
            classification.response,
            classification.error,
        )
    )
    if source is None:
        request = next(
            (
                item
                for item in (spacy.request, gliner.request, classification.request)
                if item is not None
            ),
            None,
        )
        if request is None:
            raise ValueError("Source text is unavailable because no native request was saved.")
        source = read_text(request["text"], nonblank=True)
    return render_saved_reports(
        source,
        spacy,
        gliner,
        classification=classification if has_classification else None,
        process_error=process_error,
    )


def select_summary(combined: str, artifact_names: tuple[str, str]) -> tuple[str, bool]:
    """Never truncate evidence or point at an unuploaded combined report."""
    if len(combined.encode("utf-8")) <= SUMMARY_MAX_BYTES:
        return combined, False
    spacy, gliner = (render_cell(name) for name in artifact_names)
    return (
        "**The combined report exceeds GitHub's 1 MiB per-step summary limit.**\n\n"
        f"Download `report.md` from the <code>{spacy}</code> artifact for the complete "
        f"spaCy report and from the <code>{gliner}</code> artifact for the complete "
        "GLiNER report. Each report contains the source and its full provider section; "
        "neither report is truncated.\n",
        True,
    )


def write_provider_reports(directory: Path, reports: Reports) -> bool:
    failed = False
    for provider, content in (("spacy", reports.spacy), ("gliner", reports.gliner)):
        try:
            write_atomic(directory / provider / "report.md", content.encode("utf-8"))
        except OSError:
            print(f"The {provider} report could not be written.", file=sys.stderr)
            failed = True
    return failed


def deliver_reports(
    directory: Path,
    summary: Path,
    source: str,
    artifact_names: tuple[str, str],
    *,
    spacy_error: str | None = None,
    gliner_error: str | None = None,
    classification_error: str | None = None,
    process_error: str | None = None,
) -> bool:
    reports = read_saved_reports(
        directory,
        source,
        spacy_error=spacy_error,
        gliner_error=gliner_error,
        classification_error=classification_error,
        process_error=process_error,
    )
    write_failed = write_provider_reports(directory, reports)
    content, oversized = select_summary(reports.combined, artifact_names)
    if write_failed:
        content += (
            "\n**Artifact error:** A provider report could not be written; inspect the logs.\n"
        )
    with summary.open("a", encoding="utf-8", newline="\n") as destination:
        destination.write(content)
    return reports.failed or write_failed or oversized


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate reports from saved native files.")
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    reports = read_saved_reports(args.directory)
    write_failed = write_provider_reports(args.directory, reports)
    return int(reports.failed or write_failed)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, ValueError):
        print("Report regeneration failed; inspect the saved native files.", file=sys.stderr)
        raise SystemExit(1) from None
