/** Identify local parser failures separately from source content failures. */
export class ParserError extends Error {
  constructor(readonly reason: "parser-timeout" | "parser-cancelled" | "parser-failed") {
    super(reason);
  }
}
