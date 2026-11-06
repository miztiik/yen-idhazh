"""How are only named model files resolved in one immutable local snapshot?"""

from pathlib import Path

from summary_evaluator.shared.contracts.service_settings import ModelAssetSettings


def resolve_snapshot(selection: ModelAssetSettings, cache: Path, *, local_only: bool) -> Path:
    from huggingface_hub import hf_hub_download

    directory: Path | None = None
    for filename in selection.files:
        asset = Path(
            hf_hub_download(
                repo_id=selection.reference,
                revision=selection.revision,
                filename=filename,
                cache_dir=str(cache),
                local_files_only=local_only,
            )
        )
        if asset.name != filename or asset.parent.name != selection.revision:
            raise ValueError("The asset does not identify the selected revision")
        if directory is not None and asset.parent != directory:
            raise ValueError("The selected assets do not share an immutable snapshot")
        directory = asset.parent
    if directory is None:
        raise ValueError("The selected asset inventory is empty")
    return directory
