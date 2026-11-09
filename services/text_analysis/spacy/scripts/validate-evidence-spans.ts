/** Do evidence offsets reproduce exact source text using Python's code-point indexes? */
export function validateEvidenceOffsets(
  sourceCodePoints: readonly string[],
  start: number,
  end: number,
  spanText: string,
): void {
  if (
    start < 0 ||
    end <= start ||
    end > sourceCodePoints.length ||
    sourceCodePoints.slice(start, end).join("") !== spanText
  ) {
    throw new Error("Evidence offsets do not reproduce the source");
  }
}
