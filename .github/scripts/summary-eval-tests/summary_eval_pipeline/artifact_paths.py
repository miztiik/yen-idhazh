"""Which validated directories does preparation expose to workflow artifact consumers?"""

from pathlib import Path

from .settings import PipelineSettings


def write_artifact_paths(settings: PipelineSettings, destination: Path) -> None:
    encoded = (
        f"output_directory={settings.output_directory}\n"
        f"native_log_directory={settings.native_log_directory}\n"
    )
    with destination.open("a", encoding="utf-8", newline="\n") as output:
        output.write(encoded)
