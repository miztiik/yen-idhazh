/** Do the probe's evidence checks accept exact code-point spans and reject invalid evidence? */
import { expect, test } from "bun:test";
import { validateEvidenceOffsets } from "./validate-evidence-spans.ts";

test("accepts unchanged ASCII and BMP source spans", () => {
  const sourceCodePoints = Array.from("Ada \u5317\u4EAC");
  expect(() => validateEvidenceOffsets(sourceCodePoints, 0, 3, "Ada")).not.toThrow();
  expect(() => validateEvidenceOffsets(sourceCodePoints, 4, 6, "\u5317\u4EAC")).not.toThrow();
});

test("reuses code points for spans containing and following non-BMP characters", () => {
  const source = "\u{1F680} Ada \u{1F680} Bob";
  const sourceCodePoints = Array.from(source);
  expect(() => validateEvidenceOffsets(sourceCodePoints, 2, 5, "Ada")).not.toThrow();
  expect(() => validateEvidenceOffsets(sourceCodePoints, 8, 11, "Bob")).not.toThrow();
  expect(() => validateEvidenceOffsets(sourceCodePoints, 0, 11, source)).not.toThrow();
});

test("rejects UTF-16 offsets after a non-BMP character", () => {
  const sourceCodePoints = Array.from("\u{1F680} Ada met Bob.");
  expect(() => validateEvidenceOffsets(sourceCodePoints, 3, 6, "Ada")).toThrow(
    "Evidence offsets do not reproduce the source",
  );
});

test.each([
  { start: -1, end: 1, spanText: "a" },
  { start: 0, end: 0, spanText: "" },
  { start: 2, end: 1, spanText: "" },
  { start: 3, end: 4, spanText: "" },
  { start: 0, end: 4, spanText: "Ada" },
])("rejects invalid bounds %j", ({ start, end, spanText }) => {
  expect(() => validateEvidenceOffsets(Array.from("Ada"), start, end, spanText)).toThrow(
    "Evidence offsets do not reproduce the source",
  );
});

test("rejects evidence for an empty source", () => {
  expect(() => validateEvidenceOffsets([], 0, 1, "")).toThrow(
    "Evidence offsets do not reproduce the source",
  );
});

test("requires exact source text without case or Unicode normalization", () => {
  const sourceCodePoints = Array.from("\u{1F680} e\u0301");
  expect(() => validateEvidenceOffsets(sourceCodePoints, 2, 4, "e\u0301")).not.toThrow();
  expect(() => validateEvidenceOffsets(sourceCodePoints, 2, 4, "\u00E9")).toThrow(
    "Evidence offsets do not reproduce the source",
  );
  expect(() => validateEvidenceOffsets(sourceCodePoints, 2, 4, "E\u0301")).toThrow(
    "Evidence offsets do not reproduce the source",
  );
});
