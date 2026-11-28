/** Interpret Retry-After as a delay from receipt of the target headers (RFC 9110). */
const weekday = "(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)";
const month = "(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)";
const asctime = new RegExp(`^(${weekday}) (${month}) ( [1-9]|[0-9]{2}) (\\d{2}:\\d{2}:\\d{2}) (\\d{4})$`);
const rfc850 = new RegExp(`^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), (\\d{2})-(${month})-(\\d{2}) (\\d{2}:\\d{2}:\\d{2}) GMT$`);

function canonicalHttpDate(value: string, now: number): string {
  const legacy = rfc850.exec(value);
  if (legacy !== null) {
    const [, day, date, name, year, time] = legacy;
    const maxYear = new Date(now).getUTCFullYear() + 50;
    const candidate = Math.floor(maxYear / 100) * 100 + Number(year);
    return `${day!.slice(0, 3)}, ${date} ${name} ${candidate > maxYear ? candidate - 100 : candidate} ${time} GMT`;
  }
  const abbreviated = asctime.exec(value);
  if (abbreviated === null) return value;
  const [, day, name, date, time, year] = abbreviated;
  return `${day}, ${date!.trim().padStart(2, "0")} ${name} ${year} ${time} GMT`;
}

export function readRetryAfter(raw: string | null, now: number) {
  if (raw === null) return { basis: "missing-retry-after" } as const;
  const value = raw.trim();
  if (/^[0-9]+$/.test(value)) {
    return { basis: "retry-after-seconds", delay_ms: Math.min(Number(value) * 1000, Number.MAX_SAFE_INTEGER) } as const;
  }
  const canonical = canonicalHttpDate(value, now);
  const date = new Date(canonical);
  if (date.toUTCString() !== canonical || !Number.isFinite(date.getTime())) return { basis: "invalid-retry-after" } as const;
  return { basis: "retry-after-date", delay_ms: Math.max(0, date.getTime() - now) } as const;
}
