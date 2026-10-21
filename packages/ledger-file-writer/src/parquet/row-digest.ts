/** Serializes stored rows as Python-compatible JSON lines and hashes those bytes. */
import { createHash } from "node:crypto";

export type ScalarKind = "string" | "int64" | "float64" | "bool";

export type LogicalType = {
  kind: "scalar" | "list" | "struct";
  scalar?: ScalarKind;
  nullable: boolean;
  itemType?: LogicalType;
  itemNullable?: boolean;
  fields?: LogicalField[];
};

export type LogicalField = {
  name: string;
  type: LogicalType;
  nullable: boolean;
};

function escapeAsciiJsonString(value: string): string {
  return JSON.stringify(value).replace(/[\u007f-\uffff]/g, (character) =>
    `\\u${character.charCodeAt(0).toString(16).padStart(4, "0")}`,
  );
}

function formatPythonFloat(value: number): string {
  if (!Number.isFinite(value)) throw new TypeError("non-finite float cannot be written to a ledger");
  if (Object.is(value, -0)) return "-0.0";

  const sign = value < 0 ? "-" : "";
  const [mantissa = "", exponentText] = Math.abs(value).toString().toLowerCase().split("e");
  const exponent = exponentText === undefined ? 0 : Number(exponentText);
  const [whole = "", fraction = ""] = mantissa.split(".");
  const combined = whole + fraction;
  const leadingZeroes = combined.match(/^0*/)?.[0].length ?? 0;
  const digits = combined.slice(leadingZeroes).replace(/0+$/, "");
  if (digits.length === 0) return "0.0";

  const decimalPosition = whole.length + exponent - leadingZeroes;
  const scientificExponent = decimalPosition - 1;
  if (scientificExponent < -4 || scientificExponent >= 16) {
    const significand = digits.length === 1 ? digits : `${digits[0]}.${digits.slice(1)}`;
    const exponentSign = scientificExponent < 0 ? "-" : "+";
    const magnitude = Math.abs(scientificExponent).toString().padStart(2, "0");
    return `${sign}${significand}e${exponentSign}${magnitude}`;
  }
  if (decimalPosition <= 0) {
    return `${sign}0.${"0".repeat(-decimalPosition)}${digits}`;
  }
  if (decimalPosition >= digits.length) {
    return `${sign}${digits}${"0".repeat(decimalPosition - digits.length)}.0`;
  }
  return `${sign}${digits.slice(0, decimalPosition)}.${digits.slice(decimalPosition)}`;
}

function serializeCanonicalValue(value: unknown, type: LogicalType, fieldName: string): string {
  if (value === null) {
    if (!type.nullable) throw new TypeError(`${fieldName} is null but its contract is not nullable`);
    return "null";
  }
  if (type.kind === "scalar") {
    switch (type.scalar) {
      case "string":
        if (typeof value !== "string") throw new TypeError(`${fieldName} is not a string`);
        return escapeAsciiJsonString(value);
      case "int64":
        if (typeof value !== "number" || !Number.isSafeInteger(value)) {
          throw new TypeError(`${fieldName} is not a safe integer`);
        }
        return String(value);
      case "float64":
        if (typeof value !== "number") throw new TypeError(`${fieldName} is not a number`);
        return formatPythonFloat(value);
      case "bool":
        if (typeof value !== "boolean") throw new TypeError(`${fieldName} is not a boolean`);
        return value ? "true" : "false";
      default:
        throw new TypeError(`${fieldName} has an unsupported scalar type`);
    }
  }
  if (type.kind === "list") {
    if (!Array.isArray(value) || type.itemType === undefined) {
      throw new TypeError(`${fieldName} is not a declared list`);
    }
    return `[${value.map((item, index) =>
      serializeCanonicalValue(item, { ...type.itemType!, nullable: type.itemNullable ?? false }, `${fieldName}[${index}]`),
    ).join(",")}]`;
  }
  if (type.kind === "struct") {
    if (typeof value !== "object" || value === null || Array.isArray(value) || type.fields === undefined) {
      throw new TypeError(`${fieldName} is not a declared object`);
    }
    const record = value as Record<string, unknown>;
    const declared = new Map(type.fields.map((field) => [field.name, field]));
    const keys = Object.keys(record).sort();
    if (keys.some((key) => !declared.has(key))) {
      throw new TypeError(`${fieldName} contains an undeclared field`);
    }
    return `{${keys.map((key) => {
      const field = declared.get(key);
      if (field === undefined) throw new TypeError(`${fieldName}.${key} is undeclared`);
      return `${escapeAsciiJsonString(key)}:${serializeCanonicalValue(record[key], field.type, `${fieldName}.${key}`)}`;
    }).join(",")}}`;
  }
  throw new TypeError(`${fieldName} has an unsupported logical type`);
}

export function serializeRowsBytes(rows: readonly Record<string, unknown>[], fields: readonly LogicalField[]): Buffer {
  const declared = new Map(fields.map((field) => [field.name, field]));
  const lines = rows.map((row) => {
    const keys = Object.keys(row).sort();
    if (keys.length !== declared.size || keys.some((key) => !declared.has(key))) {
      throw new TypeError("stored row fields do not match the declared Arrow columns");
    }
    return `{${keys.map((key) => {
      const field = declared.get(key);
      if (field === undefined) throw new TypeError(`stored row contains undeclared field ${key}`);
      return `${escapeAsciiJsonString(key)}:${serializeCanonicalValue(row[key], field.type, key)}`;
    }).join(",")}}\n`;
  });
  return Buffer.from(lines.join(""), "ascii");
}

export function digestRows(rows: readonly Record<string, unknown>[], fields: readonly LogicalField[]): string {
  return createHash("sha256").update(serializeRowsBytes(rows, fields)).digest("hex");
}
