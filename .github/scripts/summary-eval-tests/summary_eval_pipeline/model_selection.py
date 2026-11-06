"""How does one committed declaration supply the actual weights and request settings?"""

import hashlib
import ipaddress
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Self
from urllib.parse import urlsplit

from pydantic import Field, TypeAdapter, model_validator

from idhazh.config import refuse_a_model_nothing_could_run
from idhazh.contracts.app_config import AppConfig, ModelsFile
from idhazh.contracts.knobs.models import ModelEntry, ModelsConfig
from utilities.model_refs import list_model_files, resolve_under_config

from .contracts import ModelSelection, WorkflowContract
from .failures import WorkflowError


class NativeGenerationSettings(WorkflowContract):
    base_url: str
    request_timeout_ms: Annotated[float, Field(gt=0, allow_inf_nan=False)]

    @model_validator(mode="after")
    def require_private_origin(self) -> Self:
        try:
            parts = urlsplit(self.base_url)
            private = ipaddress.ip_address(parts.hostname or "").is_loopback
            valid = (
                parts.scheme == "http"
                and private
                and parts.port is not None
                and parts.port > 0
                and parts.username is None
                and parts.password is None
                and parts.path in ("", "/")
                and not parts.query
                and not parts.fragment
            )
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("model_server.base_url must name one private loopback HTTP origin")
        return self


@dataclass(frozen=True)
class SelectedModel:
    identity: ModelSelection
    entry: ModelEntry
    native: NativeGenerationSettings


def select_model(root: Path, named: str) -> SelectedModel:
    try:
        config = root / "config"
        app = AppConfig.from_json((config / "idhazh.json").read_text(encoding="utf-8"))
        wanted = TypeAdapter(ModelsFile).validate_python(named.strip() or app.models_file)
        path = resolve_under_config(wanted, root=config)
        encoded = path.read_bytes()
        models = ModelsConfig.from_json(encoded.decode("utf-8"))
        refuse_a_model_nothing_could_run(wanted, models)
        files = list_model_files(config, wanted)
        entry = models.summarizer
        native = NativeGenerationSettings(
            base_url=app.model_server.base_url,
            request_timeout_ms=entry.request_timeout_minutes * 60_000,
        )
        return SelectedModel(
            ModelSelection(
                models_file=wanted,
                declaration_sha256=hashlib.sha256(encoded).hexdigest(),
                model_id=entry.id,
                repo=files[0].repo,
                revision=files[0].revision,
                filename=files[0].file,
                sha256=files[0].sha256,
                quantisation=entry.quantisation,
            ),
            entry,
            native,
        )
    except (OSError, ValueError, KeyError, TypeError, SystemExit):
        raise WorkflowError("MODEL_INVALID", "input") from None


def stage_configuration(root: Path, directory: Path, selected: SelectedModel) -> None:
    """Copy only named inputs; select task instruments without editing shared defaults."""
    names = (
        "idhazh.json",
        "hono-server.json",
        "host-fingerprints.json",
        "host-probes.json",
        "ledgers.json",
    )
    destination = directory / "config"
    destination.mkdir(parents=True, exist_ok=True)
    for name in names:
        encoded = (root / "config" / name).read_bytes()
        if name in ("idhazh.json", "host-probes.json"):
            value = json.loads(encoded)
            if name == "idhazh.json":
                value["models_file"] = selected.identity.models_file
            else:
                value["task_profile"].update(
                    enabled=True, memory_enabled=False, machine_memory_enabled=True
                )
            encoded = json.dumps(value).encode("utf-8")
        (destination / name).write_bytes(encoded)
    model_path = destination / selected.identity.models_file
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_bytes((root / "config" / selected.identity.models_file).read_bytes())


def verify_staged_selection(directory: Path, selected: SelectedModel) -> None:
    try:
        configuration = directory / "config"
        encoded = (configuration / selected.identity.models_file).read_bytes()
        staged = AppConfig.from_json((configuration / "idhazh.json").read_text(encoding="utf-8"))
        if (
            hashlib.sha256(encoded).hexdigest() != selected.identity.declaration_sha256
            or staged.models_file != selected.identity.models_file
            or staged.model_server.base_url != selected.native.base_url
        ):
            raise WorkflowError("RECEIPT_INVALID", "input")
    except (OSError, ValueError):
        raise WorkflowError("RECEIPT_INVALID", "input") from None
