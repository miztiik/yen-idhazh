"""How does one admitted schema run directly on the loaded GLiNER2 model?"""

from gliner_api.declare_analysis_contracts import AnalyzeTextRequest, AnalyzeTextResult
from gliner_api.load_model import NativeModel, require_record_capability
from gliner_api.load_settings import GlinerSettings
from gliner_api.validate_analysis_results import validate_analysis_results


def analyze_text(
    model: NativeModel, request: AnalyzeTextRequest, settings: GlinerSettings
) -> AnalyzeTextResult:
    """Keep native long-text chunking, confidence and global source offsets."""
    if any(
        structure.mode is not None
        for structure in (request.analysis_schema.structures or {}).values()
    ):
        require_record_capability(model)
    raw = model.extract_long(
        request.text,
        request.analysis_schema.to_native_schema(settings.entity_confidence_threshold),
        include_confidence=request.include_confidence,
        include_spans=request.include_spans,
        overlap_policy=settings.overlap_policy,
    )
    return validate_analysis_results(raw, request)
