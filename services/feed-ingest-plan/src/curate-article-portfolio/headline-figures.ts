/** Do two supported headlines disagree about a written figure? */
// Written-number syntax and scales are the existing story_key format, not tuning knobs.
const scales: Readonly<Record<string, number>> = {
  k: 1e3, thousand: 1e3, m: 1e6, mn: 1e6, million: 1e6,
  b: 1e9, bn: 1e9, billion: 1e9, tn: 1e12, trillion: 1e12, lakh: 1e5, crore: 1e7,
};
type StoryKey = { shape: string; numbers: { value: number; significant: number }[] };

function reduceHeadline(title: string): StoryKey | null {
  const folded = title.normalize("NFKC").toLowerCase();
  // Full Unicode case-folding is not supplied here. Do not claim parity for it.
  if (/[^\x00-\x7f]/.test(folded)) return null;
  const numbers: StoryKey["numbers"] = [];
  const words = folded.replace(
    /(?<![\w.])(\d[\d,]*(?:\.\d+)?)\s*(bn|b|k|m|mn|tn|thousand|million|billion|trillion|crore|lakh)?\b/gi,
    (_match, digits: string, scale: string | undefined) => {
      const plain = digits.replaceAll(",", "");
      numbers.push({
        value: Number(plain) * (scale === undefined ? 1 : scales[scale.toLowerCase()]!),
        significant: plain.replace(".", "").replace(/^0+/, "").length || 1,
      });
      return " ";
    },
  );
  if (numbers.some(number => !Number.isFinite(number.value))) return null;
  const shape = words.replace(/[^a-z0-9]/g, " ").replace(/\s+/g, " ").trim();
  return shape === "" || shape === "untitled item" ? null : { shape, numbers };
}

function roundWritten(value: number, significant: number): number {
  if (value === 0) return 0;
  const power = 10 ** (Math.floor(Math.log10(Math.abs(value))) - significant + 1);
  const scaled = value / power;
  const floor = Math.floor(scaled);
  // Match the existing nearest-even rule at exact halves.
  const rounded = scaled - floor === 0.5 ? floor + (floor % 2) : Math.round(scaled);
  return rounded * power;
}

export function compareHeadlineFigures(left: string, right: string): Readonly<{ available: boolean; clash: boolean }> {
  const one = reduceHeadline(left);
  const other = reduceHeadline(right);
  return {
    available: one !== null && other !== null,
    clash: one !== null && other !== null && one.shape === other.shape
      && one.numbers.length === other.numbers.length
      && one.numbers.some((number, index) => {
        const second = other.numbers[index]!;
        const precision = Math.min(number.significant, second.significant);
        return roundWritten(number.value, precision) !== roundWritten(second.value, precision);
      }),
  };
}
