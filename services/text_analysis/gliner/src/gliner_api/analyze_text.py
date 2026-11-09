"""How does one admitted schema run directly on the loaded GLiNER2 model?"""

from gliner_api.declare_analysis_contracts import AnalyzeTextRequest, AnalyzeTextResult
from gliner_api.load_model import NativeModel
from gliner_api.validate_analysis_results import validate_analysis_results


def analyze_text(model: NativeModel, request: AnalyzeTextRequest) -> AnalyzeTextResult:
    """Keep native long-text chunking, confidence and global source offsets."""
    raw = model.extract_long(
        request.text,
        request.analysis_schema.to_native_schema(),
        include_confidence=True,
        include_spans=True,
    )
    return validate_analysis_results(raw, request)
