"""Which verified upstream converter constructs the real legacy dimension-call dictionaries?"""

import hashlib
import importlib.util
from pathlib import Path
from typing import cast

from summary_evaluator.source_coverage.contracts.model_call import ConvertInput
from summary_evaluator.source_coverage.contracts.service_settings import CoverageSettings


def load_converter(settings: CoverageSettings, root: Path) -> ConvertInput:
    selected = settings.assets.code
    path = root / settings.assets.cache_directory / "code" / selected.revision / "utils.py"
    if path.stat().st_size > selected.max_file_bytes or hashlib.sha256(
        path.read_bytes()
    ).hexdigest() != selected.files["utils.py"]:
        raise ValueError("The legacy input converter differs from the declared code")
    spec = importlib.util.spec_from_file_location("summary_coverage_convert", path)
    if spec is None or spec.loader is None:
        raise ValueError("The named legacy input converter could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(ConvertInput, module.convert_to_json)
