"""How is one caller-defined native GLiNER classification request collected?"""

import json
from pathlib import Path

import httpx
from collect_operations import Outcome
from collect_results import Inputs, send_request
from gliner_api.declare_analysis_contracts import AnalyzeTextRequest, AnalyzeTextResult
from gliner_api.declare_api_contracts import ANALYZE_TEXT_PATH, ErrorResult
from gliner_api.validate_analysis_results import validate_analysis_results
from prepare_default_tasks import default_classification_tasks
from pydantic import ValidationError
from render_classifications import read_classification_tasks


async def collect_classifications(
    client: httpx.AsyncClient, inputs: Inputs, root: Path, directory: Path
) -> Outcome:
    """Forward native task data once, preserving exact source and independent failures."""
    try:
        if inputs.classification_tasks.strip():
            tasks = json.loads(inputs.classification_tasks)
        else:
            from idhazh.contracts.taxonomy import Taxonomy

            taxonomy = Taxonomy.model_validate_json(
                (root / "config" / "taxonomy.json").read_bytes()
            )
            tasks = default_classification_tasks(taxonomy.model_dump(mode="json"))
        request = AnalyzeTextRequest.model_validate_json(
            json.dumps(
                {
                    "text": inputs.text,
                    "schema": {
                        "classifications": [
                            {"task": name, **task}
                            for name, task in read_classification_tasks(tasks).items()
                        ]
                    },
                }
            ),
            strict=True,
        )
    except ImportError:
        return Outcome(
            error="Default GLiNER classification tasks need the taxonomy schema; "
            "supply native classification_tasks JSON or expose the backend source root."
        )
    except ValidationError:
        return Outcome(
            error="The GLiNER classification tasks or default taxonomy failed native validation."
        )
    except (OSError, KeyError, ValueError):
        return Outcome(
            error="The GLiNER classification tasks could not be prepared; "
            "supply native tasks JSON or a valid default taxonomy."
        )
    try:
        response = await send_request(
            client,
            ANALYZE_TEXT_PATH,
            request.model_dump_json(by_alias=True, exclude_unset=True).encode("utf-8"),
            directory / "gliner" / "classification",
        )
        if response.status_code == 200:
            wire = AnalyzeTextResult.model_validate_json(response.content)
            result = validate_analysis_results(wire.result, request)
            return Outcome(result=result.model_dump(mode="json"))
        error = ErrorResult.model_validate_json(response.content)
        return Outcome(error=f"{error.error.code}: {error.error.message}")
    except (httpx.HTTPError, OSError, ValidationError, ValueError):
        return Outcome(
            error="The GLiNER classification request failed or returned an invalid response."
        )
