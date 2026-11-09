"""How is one native GLiNER classification request built and collected from the taxonomy?"""

from pathlib import Path

import httpx
from collect_operations import Outcome
from collect_results import Inputs, send_request
from gliner_api.declare_api_contracts import (
    CLASSIFY_PATH,
    ClassificationRequest,
    ClassificationResult,
    ErrorResult,
)
from pydantic import ValidationError
from render_classifications import (
    active_classification_tasks,
    read_classification_selections,
    read_classification_tasks,
)
from write_reports import write_atomic


async def collect_classifications(
    client: httpx.AsyncClient, inputs: Inputs, root: Path, directory: Path
) -> Outcome:
    """Offer active definitions once, preserving exact source and native evidence."""
    try:
        from idhazh.contracts.taxonomy import Taxonomy

        native = (root / "config" / "taxonomy.json").read_bytes()
        taxonomy = Taxonomy.model_validate_json(native)
        write_atomic(directory / "gliner" / "taxonomy.json", native)
        request = ClassificationRequest.model_validate(
            {
                "text": inputs.text,
                "tasks": active_classification_tasks(taxonomy.model_dump(mode="json")),
            }
        )
    except ImportError:
        return Outcome(
            error="The GLiNER classification Taxonomy schema is unavailable; "
            "expose the backend source root without installing the backend runtime."
        )
    except ValidationError:
        return Outcome(
            error="The GLiNER classification taxonomy or request failed native validation; "
            "every active taxonomy entry requires a definition."
        )
    except (OSError, KeyError, ValueError):
        return Outcome(
            error="The GLiNER classification taxonomy could not be prepared; "
            "active offerings must be nonempty and their definitions nonblank."
        )
    try:
        response = await send_request(
            client,
            CLASSIFY_PATH,
            request.model_dump_json().encode("utf-8"),
            directory / "gliner" / "classification",
        )
        if response.status_code == 200:
            result = ClassificationResult.model_validate_json(response.content)
            read_classification_selections(
                result.model_dump(mode="json"),
                read_classification_tasks(request.model_dump(mode="json")["tasks"]),
            )
            return Outcome(result=result.model_dump(mode="json"))
        error = ErrorResult.model_validate_json(response.content)
        return Outcome(error=f"{error.error.code}: {error.error.message}")
    except (httpx.HTTPError, OSError, ValidationError, ValueError):
        return Outcome(
            error="The GLiNER classification request failed or returned an invalid response."
        )
